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
    ChallengeTrack,
    CheckinRequest,
    CheckInResponse,
    ChecklistToggleResponse,
    DailyChecklistResponse,
    HeatmapResponse,
    JoinChallengeRequest,
    MonthlyCalendarResponse,
    MyTrackResponse,
    UpdateMyTrackRequest,
    UserChallengeListResponse,
    UserChallengeResponse,
    WeeklyEmotionResponse,
)
from app.dtos.slump import (
    SlumpMicroCheckinRequest,
    SlumpMicroCheckinResponse,
    SlumpStatusResponse,
)
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
    "/my-track",
    response_model=MyTrackResponse,
    status_code=status.HTTP_200_OK,
    summary="내 트랙 조회",
    description="사용자의 현재 챌린지 트랙(CARE / WELLNESS)을 반환합니다.",
)
async def get_my_track(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.get_my_track(user_id=user.id)
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@challenge_router.put(
    "/my-track",
    response_model=MyTrackResponse,
    status_code=status.HTTP_200_OK,
    summary="배지 단계 변경",
    description="사용자의 배지 단계(stage)를 변경합니다. 트랙은 자동배정되어 변경할 수 없습니다.",
)
async def update_my_track(
    body: UpdateMyTrackRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.update_my_track(user_id=user.id, stage=body.stage)
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@challenge_router.get(
    "/daily-checklist",
    response_model=DailyChecklistResponse,
    status_code=status.HTTP_200_OK,
    summary="오늘의 필수체크 목록 조회",
    description="사용자의 트랙에 맞는 오늘의 필수 체크리스트 항목과 완료 여부를 반환합니다.",
)
async def get_daily_checklist(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.get_daily_checklist(user_id=user.id, today=date.today())
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@challenge_router.post(
    "/daily-checklist/{item_key}",
    response_model=ChecklistToggleResponse,
    status_code=status.HTTP_200_OK,
    summary="필수체크 항목 토글",
    description="오늘의 필수체크 항목을 완료/취소 토글하고 포인트·알 성장 적립 결과를 반환합니다.",
)
async def toggle_daily_checklist(
    item_key: str,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.toggle_daily_checklist(user_id=user.id, item_key=item_key, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@challenge_router.get(
    "",
    response_model=ChallengeListResponse,
    status_code=status.HTTP_200_OK,
    summary="챌린지 목록 조회",
    description=(
        "track·stage 쿼리 파라미터로 챌린지 목록을 필터링합니다. "
        "track 미입력 시 전체 트랙, stage 미입력 시 전체 단계 반환."
    ),
)
async def list_challenges(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
    track: Annotated[ChallengeTrack | None, Query(description="챌린지 트랙 (CARE / WELLNESS)")] = None,
    stage: Annotated[int | None, Query(ge=1, le=5, description="CKD 단계 (1~5)")] = None,
) -> Response:
    result = await service.list_challenges(track=track, stage=stage)
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
    description=("오늘 체크인을 취소합니다. total_checkins·streak_count 롤백, 포인트 역적립, COMPLETED→ACTIVE 복귀."),
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
        "오늘 체크인한 경우 당일 지급 포인트는 회수되고 카운트가 롤백됩니다(과거 보상은 보존)."
    ),
)
async def abandon_challenge(
    user_challenge_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.abandon(user_id=user.id, user_challenge_id=user_challenge_id, today=date.today())
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


@challenge_router.get(
    "/calendar",
    response_model=MonthlyCalendarResponse,
    status_code=status.HTTP_200_OK,
    summary="월별 달성 달력",
    description="날짜별 달성 단계(none/basic/silver/gold)와 월 통계. year_month 미지정 시 당월.",
)
async def get_monthly_calendar(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
    year_month: Annotated[str | None, Query(description="YYYY-MM, 미지정 시 당월")] = None,
) -> Response:
    result = await service.get_monthly_calendar(user_id=user.id, year_month=year_month)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
