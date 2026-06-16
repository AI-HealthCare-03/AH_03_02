from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

from app.models.admin_action_log import AdminAction, TargetType


# ── 사용자 관리 ─────────────────────────────────────
class AdminUserRow(BaseModel):
    """사용자 목록 행 (PII 마스킹 적용)."""

    id: int
    email_masked: str
    name_masked: str
    gender: str
    is_active: bool
    is_admin: bool
    email_verified: bool
    last_login: datetime | None
    created_at: datetime


class AdminUserListResponse(BaseModel):
    total: int
    items: list[AdminUserRow]


class AdminUserDetailResponse(BaseModel):
    """사용자 상세 (PII 마스킹 + 검진 수치 범주화)."""

    id: int
    email_masked: str
    name_masked: str
    phone_masked: str
    gender: str
    age: int  # 생년월일 원본 대신 만 나이 (PII 보호 — 검진 수치 범주화와 일관)
    is_active: bool
    is_admin: bool
    email_verified: bool
    failed_login_count: int
    locked_until: datetime | None
    last_login: datetime | None
    created_at: datetime
    # 검진 요약 (수치 X, 범주만)
    latest_health_summary: dict | None = None


class AdminImpersonateTarget(BaseModel):
    id: int
    name_masked: str


class AdminImpersonateResponse(BaseModel):
    """읽기전용 임퍼소네이션 view 토큰 발급 응답."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 초 단위
    target: AdminImpersonateTarget


# ── 챌린지 카탈로그 관리 ─────────────────────────────
class AdminChallengeCreateRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    category: Annotated[str, Field(description="HYDRATION/EXERCISE/DIET/SLEEP/STRESS")]
    description: str
    duration_days: Annotated[int, Field(ge=1, le=365)]
    track: Annotated[str, Field(description="A/B")]
    stage: Annotated[int, Field(ge=1, le=4)] = 1


class AdminChallengeUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    duration_days: int | None = None
    is_active: bool | None = None


class AdminChallengeResponse(BaseModel):
    id: int
    name: str
    category: str
    description: str
    duration_days: int
    track: str
    stage: int
    is_active: bool
    created_at: datetime


class AdminChallengeListResponse(BaseModel):
    total: int
    items: list[AdminChallengeResponse]


# ── 위험 액션 사유 입력 (감사 가치 ↑) ─────────────────────────
class AdminUserActionRequest(BaseModel):
    reason: Annotated[str | None, Field(default=None, max_length=500, description="사유 (정지·강제 탈퇴 권장)")] = None


class AdminChallengeDeactivateRequest(BaseModel):
    reason: Annotated[str | None, Field(default=None, max_length=500, description="비활성화 사유")] = None


# ── 통계 ────────────────────────────────────────────
class SignupBucket(BaseModel):
    date: str  # YYYY-MM-DD
    count: int


class AdminStatsSummary(BaseModel):
    total_users: int
    active_users: int
    email_verified_users: int
    new_users_7d: int
    new_users_30d: int
    total_health_checks: int
    total_lifestyle_surveys: int
    total_user_challenges: int
    total_checkins: int
    challenges_active_catalog: int
    ckd_stage_distribution: dict[str, int]  # G1~G5 + UNKNOWN
    challenges_by_category: dict[str, int]  # HYDRATION/EXERCISE/DIET/SLEEP/STRESS
    signups_last_30d: list[SignupBucket]  # 일별 신규 가입 시계열


# ── 감사 로그 ────────────────────────────────────────
class AdminActionLogRow(BaseModel):
    id: int
    admin_user_id: int
    action: AdminAction
    target_type: TargetType
    target_id: int
    detail: dict[str, Any]
    created_at: datetime


class AdminActionLogListResponse(BaseModel):
    total: int
    items: list[AdminActionLogRow]


# ── 세이프티 가드 이력 ───────────────────────────────
class AdminSafetyEventRow(BaseModel):
    id: int
    user_id: int
    user_email_masked: str  # 익명화된 식별자 (확인 액션 추적용)
    health_check_id: int | None
    event_type: str
    value: float
    message: str
    acknowledged: bool
    acknowledged_by: int | None
    acknowledged_at: datetime | None
    created_at: datetime


class AdminSafetyEventListResponse(BaseModel):
    total: int
    items: list[AdminSafetyEventRow]


class AdminSafetyAcknowledgeRequest(BaseModel):
    note: Annotated[str | None, Field(default=None, max_length=500, description="확인 메모 (감사 로그에 기록)")] = None
