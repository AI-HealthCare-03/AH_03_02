"""검사 수치 기록장 라우터 — /records/lab 하위 6개 엔드포인트."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.lab import (
    LabRecordResponse,
    MetricsResponse,
    OverviewResponse,
    SaveLabRequest,
    SaveLabResponse,
    SetMetricsRequest,
)
from app.models.users import User
from app.services.lab import LabService

lab_router = APIRouter(prefix="/records/lab", tags=["lab"])


@lab_router.get("/metrics", response_model=MetricsResponse, status_code=status.HTTP_200_OK)
async def get_metrics(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[LabService, Depends(LabService)],
) -> Response:
    """사용자 활성 지표 목록 및 카탈로그 전체 조회."""
    result = await service.get_metrics(user_id=user.id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.put("/metrics", response_model=MetricsResponse, status_code=status.HTTP_200_OK)
async def set_metrics(
    body: SetMetricsRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[LabService, Depends(LabService)],
) -> Response:
    """사용자가 추적할 활성 지표 키 목록을 교체."""
    result = await service.set_metrics(user_id=user.id, metric_keys=body.metric_keys)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.get("/overview", response_model=OverviewResponse, status_code=status.HTTP_200_OK)
async def get_overview(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[LabService, Depends(LabService)],
) -> Response:
    """활성 지표별 최신값·이전값·변화량·추세 포인트 요약 조회."""
    result = await service.get_overview(user_id=user.id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.get("", response_model=LabRecordResponse, status_code=status.HTTP_200_OK)
async def get_record(
    date_q: Annotated[date, Query(alias="date")],
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[LabService, Depends(LabService)],
) -> Response:
    """특정 날짜의 검사 수치 기록 조회."""
    result = await service.get_record(user_id=user.id, measured_date=date_q)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.put("", response_model=SaveLabResponse, status_code=status.HTTP_200_OK)
async def save_record(
    body: SaveLabRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[LabService, Depends(LabService)],
) -> Response:
    """검사 수치 저장 (날짜+수치 맵). 비활성 지표는 무시하며, MONITORING 챌린지 자동 체크인 수행."""
    result = await service.save_record(user_id=user.id, measured_date=body.measured_date, values=body.values)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.delete("", response_model=LabRecordResponse, status_code=status.HTTP_200_OK)
async def delete_record(
    date_q: Annotated[date, Query(alias="date")],
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[LabService, Depends(LabService)],
) -> Response:
    """특정 날짜의 검사 수치 기록 전체 삭제."""
    result = await service.delete_record(user_id=user.id, measured_date=date_q)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
