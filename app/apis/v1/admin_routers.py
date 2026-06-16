"""관리자 페이지 API — 모든 엔드포인트에 get_admin_user 가드 필수."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_admin_user
from app.dtos.admin import (
    AdminActionLogListResponse,
    AdminChallengeCreateRequest,
    AdminChallengeDeactivateRequest,
    AdminChallengeListResponse,
    AdminChallengeResponse,
    AdminChallengeUpdateRequest,
    AdminImpersonateResponse,
    AdminSafetyAcknowledgeRequest,
    AdminSafetyEventListResponse,
    AdminStatsSummary,
    AdminUserActionRequest,
    AdminUserDetailResponse,
    AdminUserListResponse,
)
from app.models.admin_action_log import AdminAction, TargetType
from app.models.safety_event import SafetyEventType
from app.models.users import User
from app.services.admin import AdminService

admin_router = APIRouter(prefix="/admin", tags=["admin"])


# ── 사용자 관리 ─────────────────────────────────────
@admin_router.get(
    "/users",
    response_model=AdminUserListResponse,
    status_code=status.HTTP_200_OK,
    summary="사용자 목록 (마스킹 적용)",
)
async def list_users(
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
    q: Annotated[str | None, Query(description="이메일/이름 검색 (원본 기준)")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    total, items = await service.list_users(q=q, limit=limit, offset=offset)
    return Response(content={"total": total, "items": items}, status_code=status.HTTP_200_OK)


@admin_router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="사용자 상세 (PII 마스킹 + 검진 수치 범주화)",
)
async def get_user_detail(
    user_id: int,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
) -> Response:
    detail = await service.get_user_detail(user_id)
    return Response(content=detail, status_code=status.HTTP_200_OK)


@admin_router.patch(
    "/users/{user_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="사용자 활성화 (감사 로그 기록)",
)
async def activate_user(
    user_id: int,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
    body: AdminUserActionRequest | None = None,
) -> Response:
    reason = body.reason if body else None
    await service.set_user_active(admin_user_id=admin.id, user_id=user_id, active=True, reason=reason)
    return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)


@admin_router.patch(
    "/users/{user_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="사용자 정지 (사유 필수, 감사 로그 기록)",
)
async def deactivate_user(
    user_id: int,
    body: AdminUserActionRequest,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
) -> Response:
    await service.set_user_active(admin_user_id=admin.id, user_id=user_id, active=False, reason=body.reason)
    return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)


@admin_router.patch(
    "/users/{user_id}/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="이메일 인증 강제 처리 (감사 로그 기록)",
)
async def force_verify_email(
    user_id: int,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
    body: AdminUserActionRequest | None = None,
) -> Response:
    reason = body.reason if body else None
    await service.force_verify_email(admin_user_id=admin.id, user_id=user_id, reason=reason)
    return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)


@admin_router.post(
    "/users/{user_id}/impersonate",
    response_model=AdminImpersonateResponse,
    status_code=status.HTTP_200_OK,
    summary="사용자 임퍼소네이션 (읽기전용 view 토큰 발급, 감사 로그)",
)
async def impersonate_user(
    user_id: int,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
) -> Response:
    result = await service.impersonate(admin_user_id=admin.id, user_id=user_id)
    return Response(content=result, status_code=status.HTTP_200_OK)


# ── 챌린지 카탈로그 ─────────────────────────────────
@admin_router.get(
    "/challenges",
    response_model=AdminChallengeListResponse,
    status_code=status.HTTP_200_OK,
    summary="챌린지 카탈로그 목록 (비활성 포함)",
)
async def list_admin_challenges(
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    total, items = await service.list_challenges(limit=limit, offset=offset)
    return Response(
        content={
            "total": total,
            "items": [
                {
                    "id": c.id,
                    "name": c.name,
                    "category": c.category,
                    "description": c.description,
                    "duration_days": c.duration_days,
                    "track": c.track,
                    "stage": c.stage,
                    "is_active": c.is_active,
                    "created_at": c.created_at.isoformat(),
                }
                for c in items
            ],
        },
        status_code=status.HTTP_200_OK,
    )


@admin_router.post(
    "/challenges",
    response_model=AdminChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="챌린지 카탈로그 추가 (감사 로그 기록)",
)
async def create_admin_challenge(
    body: AdminChallengeCreateRequest,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
) -> Response:
    ch = await service.create_challenge(admin_user_id=admin.id, data=body.model_dump())
    return Response(
        content={
            "id": ch.id,
            "name": ch.name,
            "category": ch.category,
            "description": ch.description,
            "duration_days": ch.duration_days,
            "track": ch.track,
            "stage": ch.stage,
            "is_active": ch.is_active,
            "created_at": ch.created_at.isoformat(),
        },
        status_code=status.HTTP_201_CREATED,
    )


@admin_router.patch(
    "/challenges/{challenge_id}",
    response_model=AdminChallengeResponse,
    status_code=status.HTTP_200_OK,
    summary="챌린지 카탈로그 수정 (감사 로그 기록)",
)
async def update_admin_challenge(
    challenge_id: int,
    body: AdminChallengeUpdateRequest,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
) -> Response:
    ch = await service.update_challenge(
        admin_user_id=admin.id,
        challenge_id=challenge_id,
        data=body.model_dump(exclude_none=True),
    )
    return Response(
        content={
            "id": ch.id,
            "name": ch.name,
            "category": ch.category,
            "description": ch.description,
            "duration_days": ch.duration_days,
            "track": ch.track,
            "stage": ch.stage,
            "is_active": ch.is_active,
            "created_at": ch.created_at.isoformat(),
        },
        status_code=status.HTTP_200_OK,
    )


@admin_router.delete(
    "/challenges/{challenge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="챌린지 비활성화 (soft delete, 감사 로그 기록)",
)
async def deactivate_admin_challenge(
    challenge_id: int,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
    body: AdminChallengeDeactivateRequest | None = None,
) -> Response:
    reason = body.reason if body else None
    await service.deactivate_challenge(admin_user_id=admin.id, challenge_id=challenge_id, reason=reason)
    return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)


# ── 통계 ────────────────────────────────────────────
@admin_router.get(
    "/stats/summary",
    response_model=AdminStatsSummary,
    status_code=status.HTTP_200_OK,
    summary="관리자 통계 요약 (집계만 — PHI 위반 없음)",
)
async def get_stats_summary(
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
) -> Response:
    summary = await service.stats_summary()
    return Response(content=summary, status_code=status.HTTP_200_OK)


# ── 세이프티 가드 이력 ────────────────────────────────
@admin_router.get(
    "/safety-events",
    response_model=AdminSafetyEventListResponse,
    status_code=status.HTTP_200_OK,
    summary="세이프티 가드 발동 이력 (의료 안전 모니터링)",
)
async def list_safety_events(
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    event_type: Annotated[SafetyEventType | None, Query(description="유형 필터")] = None,
    only_unacknowledged: Annotated[bool, Query(description="미확인만")] = False,
) -> Response:
    total, items = await service.list_safety_events(
        limit=limit, offset=offset, event_type=event_type, only_unacknowledged=only_unacknowledged
    )
    return Response(content={"total": total, "items": items}, status_code=status.HTTP_200_OK)


@admin_router.patch(
    "/safety-events/{event_id}/acknowledge",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="세이프티 이벤트 확인 처리 (감사 로그 기록 + PHI 노출 책임 추적)",
)
async def acknowledge_safety_event(
    event_id: int,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
    body: AdminSafetyAcknowledgeRequest | None = None,
) -> Response:
    note = body.note if body else None
    await service.acknowledge_safety_event(admin_user_id=admin.id, event_id=event_id, note=note)
    return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)


# ── 감사 로그 ────────────────────────────────────────
@admin_router.get(
    "/logs",
    response_model=AdminActionLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="관리자 액션 감사 로그 (필터 지원)",
)
async def list_admin_logs(
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[AdminAction | None, Query(description="액션 종류 필터")] = None,
    target_type: Annotated[TargetType | None, Query(description="대상 리소스 타입 필터")] = None,
    admin_user_id: Annotated[int | None, Query(description="관리자 ID 필터")] = None,
    since: Annotated[datetime | None, Query(description="시작 시각 (ISO8601)")] = None,
    until: Annotated[datetime | None, Query(description="종료 시각 (ISO8601)")] = None,
) -> Response:
    total, items = await service.list_logs(
        limit=limit,
        offset=offset,
        action=action,
        target_type=target_type,
        admin_user_id=admin_user_id,
        since=since,
        until=until,
    )
    return Response(
        content={
            "total": total,
            "items": [
                {
                    "id": log.id,
                    "admin_user_id": log.admin_user_id,
                    "action": log.action,
                    "target_type": log.target_type,
                    "target_id": log.target_id,
                    "detail": log.detail,
                    "created_at": log.created_at.isoformat(),
                }
                for log in items
            ],
        },
        status_code=status.HTTP_200_OK,
    )
