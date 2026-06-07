from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.challenge import (
    AbandonChallengeResponse,
    CancelCheckinResponse,
    CategoryProgressResponse,
    ChallengeListResponse,
    CheckinRequest,
    CheckInResponse,
    HeatmapResponse,
    JoinChallengeRequest,
    UserChallengeListResponse,
    UserChallengeResponse,
    WeeklyEmotionResponse,
)
from app.dtos.slump import (
    SlumpMicroCheckinRequest,
    SlumpMicroCheckinResponse,
    SlumpStatusResponse,
)
from app.models.health_check import AppGroup
from app.models.users import User
from app.services.challenge import ChallengeService
from app.services.slump import SlumpService

challenge_router = APIRouter(prefix="/challenges", tags=["challenges"])
user_challenge_router = APIRouter(prefix="/user-challenges", tags=["user-challenges"])


# ────────────────────────────────────────────────────────────
# REQ-CHAL-006 슬럼프 + 마이크로 챌린지
# ────────────────────────────────────────────────────────────


@challenge_router.get(
    "/slump-micro",
    response_model=SlumpStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="REQ-CHAL-006 슬럼프 상태 + 오늘의 마이크로 챌린지",
)
async def get_slump_micro(
    user: Annotated[User, Depends(get_request_user)],
    slump_service: Annotated[SlumpService, Depends(SlumpService)],
) -> Response:
    result = await slump_service.get_status(user_id=user.id, today=date.today())
    return Response(content=result, status_code=status.HTTP_200_OK)


@challenge_router.post(
    "/slump-micro/checkin",
    response_model=SlumpMicroCheckinResponse,
    status_code=status.HTTP_200_OK,
    summary="REQ-CHAL-006 마이크로 챌린지 체크인 (슬럼프 해제)",
)
async def checkin_slump_micro(
    body: SlumpMicroCheckinRequest,
    user: Annotated[User, Depends(get_request_user)],
    slump_service: Annotated[SlumpService, Depends(SlumpService)],
) -> Response:
    result = await slump_service.checkin_micro(user_id=user.id, micro_code=body.micro_code, today=date.today())
    return Response(content=result, status_code=status.HTTP_200_OK)


@challenge_router.get(
    "",
    response_model=ChallengeListResponse,
    status_code=status.HTTP_200_OK,
    summary="챌린지 목록 조회",
    description=(
        "사용자의 App 그룹(app_group)에 맞는 챌린지 목록을 반환합니다. "
        "G1·G2는 Track A(케어), G3·G4는 Track B(일반). "
        "미입력 시 최신 검진의 CKD 단계로 자동 배정 (ML 모델 미실행 fallback)."
    ),
)
async def list_challenges(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
    app_group: Annotated[AppGroup | None, Query(description="ML 모델 배정 그룹 (G1~G4)")] = None,
) -> Response:
    # ML 모델 미실행 시: 최신 검진 CKD 단계로 fallback
    if app_group is None:
        from app.models.health_check import CkdStage, HealthCheck

        latest = await HealthCheck.filter(user_id=user.id).order_by("-checked_date").first()
        if latest is None:
            from app.dtos.challenge import ChallengeListResponse

            return Response(ChallengeListResponse(total=0, items=[]).model_dump(), status_code=status.HTTP_200_OK)
        if latest.ckd_stage in (CkdStage.G3A, CkdStage.G3B, CkdStage.G4, CkdStage.G5):
            app_group = AppGroup.G3
        else:
            app_group = AppGroup.G2
    result = await service.list_challenges(app_group)
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@user_challenge_router.post(
    "",
    response_model=UserChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="챌린지 참여",
)
async def join_challenge(
    request: JoinChallengeRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.join_challenge(user_id=user.id, dto=request)
    return Response(result.model_dump(), status_code=status.HTTP_201_CREATED)


@user_challenge_router.get(
    "",
    response_model=UserChallengeListResponse,
    status_code=status.HTTP_200_OK,
    summary="내 챌린지 목록",
)
async def list_my_challenges(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    result = await service.list_my_challenges(user_id=user.id, limit=limit, offset=offset)
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@user_challenge_router.post(
    "/{user_challenge_id}/checkin",
    response_model=CheckInResponse,
    status_code=status.HTTP_200_OK,
    summary="챌린지 체크인",
    description="오늘 하루 챌린지를 완료했음을 기록합니다. 하루 1회만 가능합니다.",
)
async def checkin(
    user_challenge_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
    request: CheckinRequest | None = None,
) -> Response:
    emotion = request.emotion if request else None
    result = await service.checkin(
        user_challenge_id=user_challenge_id,
        user_id=user.id,
        today=date.today(),
        emotion=emotion,
    )
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@user_challenge_router.delete(
    "/{user_challenge_id}/checkin",
    response_model=CancelCheckinResponse,
    status_code=status.HTTP_200_OK,
    summary="체크인 취소 (완전 롤백)",
    description=(
        "오늘 체크인을 취소합니다. "
        "total_checkins·streak_count 롤백, 포인트 역적립, COMPLETED→ACTIVE 복귀."
    ),
)
async def cancel_checkin(
    user_challenge_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.cancel_checkin(
        user_id=user.id,
        user_challenge_id=user_challenge_id,
        today=date.today(),
    )
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@user_challenge_router.delete(
    "/{user_challenge_id}",
    response_model=AbandonChallengeResponse,
    status_code=status.HTTP_200_OK,
    summary="챌린지 참여 해제 (ABANDONED)",
    description=(
        "챌린지 참여를 해제합니다. 레코드 삭제 없이 상태만 ABANDONED로 변경합니다. "
        "체크인 기록과 포인트는 그대로 유지됩니다."
    ),
)
async def abandon_challenge(
    user_challenge_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.abandon(user_id=user.id, user_challenge_id=user_challenge_id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@challenge_router.get(
    "/weekly-emotion",
    response_model=WeeklyEmotionResponse,
    status_code=status.HTTP_200_OK,
    summary="주간 감정 기록 (REQ-DASH-001 ⑤)",
    description="최근 7일 일별 체크인 감정. 감정 듀얼 축 차트용.",
)
async def get_weekly_emotion(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.get_weekly_emotion(user_id=user.id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@challenge_router.get(
    "/category-progress",
    response_model=CategoryProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="카테고리별 라디알 진행률 (REQ-DASH-001 ⑥)",
    description="수분/운동/식단/수면/스트레스 5종 카테고리별 active 챌린지 평균 진행률.",
)
async def get_category_progress(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.get_category_progress(user_id=user.id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@challenge_router.get(
    "/heatmap",
    response_model=HeatmapResponse,
    status_code=status.HTTP_200_OK,
    summary="챌린지 잔디 히트맵 (REQ-DASH-001 ③)",
    description="최근 N주(기본 26주) 일별 체크인 횟수. 주 시작은 월요일.",
)
async def get_heatmap(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
    weeks: Annotated[int, Query(ge=1, le=52)] = 26,
) -> Response:
    result = await service.get_heatmap(user_id=user.id, weeks=weeks)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
