import logging
from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import ORJSONResponse as Response
from fastapi.responses import StreamingResponse

from app.dependencies.security import get_request_user
from app.dtos.health_check import (
    HealthCheckCreateRequest,
    HealthCheckListResponse,
    HealthCheckResponse,
    ReportResponse,
)
from app.models.users import User
from app.services import ocr as ocr_service
from app.services.health_check import HealthCheckService
from app.services.pdf_report import render_report_pdf

logger = logging.getLogger(__name__)

health_check_router = APIRouter(prefix="/health-checks", tags=["health-checks"])

# OCR 업로드 제한 — Clova 무료 한도(20MB·이미지)와 안전 마진 고려
_OCR_ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "application/pdf"}
_OCR_MAX_BYTES = 10 * 1024 * 1024  # 10MB


def _get_user_age(user: User) -> int:
    today = date.today()
    age = today.year - user.birthday.year
    # 생일이 아직 안 지난 경우 1 빼기
    if (today.month, today.day) < (user.birthday.month, user.birthday.day):
        age -= 1
    return age


@health_check_router.post(
    "",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_201_CREATED,
    summary="검진 결과 입력",
    description=(
        "건강검진 수치를 입력합니다. "
        "크레아티닌 값이 있으면 CKD-EPI 공식으로 eGFR을 즉시 추정하고 CKD 단계를 반환합니다. "
        "ML 기반 ckd_risk_score는 AI 워커가 비동기 처리 후 업데이트됩니다."
    ),
)
async def create_health_check(
    request: HealthCheckCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthCheckService, Depends(HealthCheckService)],
) -> Response:
    result = await service.create_health_check(
        user_id=user.id,
        user_age=_get_user_age(user),
        user_gender=user.gender,
        dto=request,
    )
    return Response(result.model_dump(), status_code=status.HTTP_201_CREATED)


@health_check_router.get(
    "",
    response_model=HealthCheckListResponse,
    status_code=status.HTTP_200_OK,
    summary="내 검진 이력 목록",
)
async def list_health_checks(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthCheckService, Depends(HealthCheckService)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    result = await service.get_health_checks(user_id=user.id, limit=limit, offset=offset)
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@health_check_router.get(
    "/{health_check_id}",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="검진 결과 단건 조회",
)
async def get_health_check(
    health_check_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthCheckService, Depends(HealthCheckService)],
) -> Response:
    result = await service.get_health_check(health_check_id=health_check_id, user_id=user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="검진 기록을 찾을 수 없습니다.",
        )
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@health_check_router.delete(
    "/{health_check_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="검진 기록 삭제",
    description="본인 소유 검진 1건 삭제. SHAP 리포트는 ON DELETE 정책에 따름.",
)
async def delete_health_check(
    health_check_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthCheckService, Depends(HealthCheckService)],
) -> Response:
    deleted = await service.delete_health_check(health_check_id=health_check_id, user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="검진 기록을 찾을 수 없습니다.")
    return Response(None, status_code=status.HTTP_204_NO_CONTENT)


@health_check_router.patch(
    "/{health_check_id}",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="검진 결과 수정",
    description=(
        "본인 소유 검진 1건 수정. 모든 필드 전체 덮어쓰기(create와 동일 페이로드). "
        "프론트는 최신 검진에만 수정 버튼을 노출하지만, 백엔드는 본인 소유면 어떤 row든 수정 허용."
    ),
)
async def update_health_check(
    health_check_id: int,
    request: HealthCheckCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthCheckService, Depends(HealthCheckService)],
) -> Response:
    result = await service.update_health_check(
        health_check_id=health_check_id,
        user_id=user.id,
        user_age=_get_user_age(user),
        user_gender=user.gender,
        dto=request,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="검진 기록을 찾을 수 없습니다.")
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@health_check_router.delete(
    "",
    status_code=status.HTTP_200_OK,
    summary="검진 기록 전체 삭제",
    description="본인의 모든 검진 기록을 한 번에 삭제. 삭제된 건수 반환.",
)
async def delete_all_health_checks(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthCheckService, Depends(HealthCheckService)],
) -> Response:
    deleted_count = await service.delete_all_health_checks(user_id=user.id)
    return Response({"deleted_count": deleted_count}, status_code=status.HTTP_200_OK)


@health_check_router.get(
    "/{health_check_id}/report",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="SHAP 리포트 + AI 행동 가이드",
    description=(
        "검진 기록의 SHAP 기반 위험 변수 분석 결과를 반환합니다. "
        "shap_model1은 CKD 위험 변수(모델1), shap_model2는 생활습관 변수(모델2) + 또래 비교입니다. "
        "ai_guide는 Task 8(RAG 연결) 이후 채워집니다."
    ),
)
async def get_report(
    health_check_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthCheckService, Depends(HealthCheckService)],
) -> Response:
    result = await service.get_report(health_check_id=health_check_id, user_id=user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="검진 기록을 찾을 수 없습니다.",
        )
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@health_check_router.get(
    "/{health_check_id}/pdf",
    status_code=status.HTTP_200_OK,
    summary="건강 리포트 PDF 다운로드",
    description="검진 기록의 리포트를 A4 PDF로 생성합니다.",
)
async def download_report_pdf(
    health_check_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthCheckService, Depends(HealthCheckService)],
) -> StreamingResponse:
    result = await service.get_report(health_check_id=health_check_id, user_id=user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="검진 기록을 찾을 수 없습니다.",
        )
    try:
        pdf_bytes = render_report_pdf(result, checked_date=date.today().isoformat())
    except Exception as exc:
        logger.exception("PDF 생성 오류 (health_check_id=%s): %s", health_check_id, exc)
        raise HTTPException(status_code=500, detail=f"PDF 생성 실패: {exc}") from exc
    filename = f"건강리포트_{date.today().isoformat()}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@health_check_router.post(
    "/ocr",
    status_code=status.HTTP_200_OK,
    summary="검진 결과지 OCR 텍스트 추출 (Clova)",
    description=(
        "검진 결과지 이미지(JPG·PNG·PDF, 최대 10MB)를 업로드하면 Clova OCR API로 텍스트를 추출합니다. "
        "추출된 텍스트와 신뢰도를 반환하고 사용자가 수동 입력 화면에서 옮겨 적습니다. "
        "Clova API 키 미설정 환경(envs/.local.env에 CLOVA_OCR_INVOKE_URL·CLOVA_OCR_SECRET_KEY 없음)에선 503 반환."
    ),
)
async def ocr_extract(
    user: Annotated[User, Depends(get_request_user)],
    file: Annotated[UploadFile, File(description="검진 결과지 이미지·PDF (≤ 10MB)")],
) -> Response:
    # 파일 형식 검증
    if file.content_type not in _OCR_ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JPG, PNG, PDF 형식만 지원합니다.",
        )

    # 본문 읽기 + 크기 검증
    contents = await file.read()
    if len(contents) > _OCR_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="파일 크기는 최대 10MB까지 지원합니다.",
        )

    # Clova OCR 호출 — 키 미설정·외부 오류·타임아웃은 서비스 안에서 한국어 HTTPException으로 변환
    result = await ocr_service.extract_text(
        file_bytes=contents,
        content_type=file.content_type or "application/octet-stream",
        filename=file.filename or "checkup",
    )
    return Response(result, status_code=status.HTTP_200_OK)
