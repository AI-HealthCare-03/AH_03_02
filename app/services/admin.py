"""관리자 페이지 서비스.

- PHI/PII 마스킹·범주화는 도메인 경계에서 수행 (CLAUDE.md §5)
- 모든 액션은 AdminActionLog에 기록 (책임 추적)
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from starlette import status
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.core.jwt.tokens import AccessToken
from app.core.utils.masking import (
    categorize_egfr,
    categorize_fasting_glucose,
    categorize_systolic_bp,
    mask_email,
    mask_name,
    mask_phone,
)
from app.core.utils.masking import mask_email as _mask_email_for_log
from app.models.admin_action_log import AdminAction, AdminActionLog, TargetType
from app.models.challenge import Challenge, UserChallenge
from app.models.health_check import HealthCheck
from app.models.lifestyle_survey import LifestyleSurvey
from app.models.safety_event import SafetyEvent, SafetyEventType
from app.models.users import User


class AdminService:
    # ── 사용자 관리 ─────────────────────────────────
    async def list_users(self, *, q: str | None, limit: int, offset: int) -> tuple[int, list[dict]]:
        qs = User.all()
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(name__icontains=q))
        total = await qs.count()
        rows = await qs.order_by("-created_at").offset(offset).limit(limit)
        items = [
            {
                "id": u.id,
                "email_masked": mask_email(u.email),
                "name_masked": mask_name(u.name),
                "gender": u.gender,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "email_verified": u.email_verified,
                "last_login": u.last_login,
                "created_at": u.created_at,
            }
            for u in rows
        ]
        return total, items

    async def get_user_detail(self, user_id: int) -> dict:
        user = await User.get_or_none(id=user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
        latest_hc = await HealthCheck.filter(user_id=user_id).order_by("-checked_date").first()
        latest_health_summary: dict | None = None
        if latest_hc:
            # CLAUDE.md §5: 원본 수치 X, 범주만 노출
            latest_health_summary = {
                "checked_date": latest_hc.checked_date.isoformat(),
                "systolic_bp_category": categorize_systolic_bp(latest_hc.systolic_bp),
                "fasting_glucose_category": categorize_fasting_glucose(latest_hc.fasting_glucose),
                "egfr_category": categorize_egfr(latest_hc.egfr_estimated),
                "ckd_stage": latest_hc.ckd_stage,
            }
        today = date.today()
        age = today.year - user.birthday.year - ((today.month, today.day) < (user.birthday.month, user.birthday.day))
        return {
            "id": user.id,
            "email_masked": mask_email(user.email),
            "name_masked": mask_name(user.name),
            "phone_masked": mask_phone(user.phone_number),
            "gender": user.gender,
            "age": age,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "email_verified": user.email_verified,
            "failed_login_count": user.failed_login_count,
            "locked_until": user.locked_until,
            "last_login": user.last_login,
            "created_at": user.created_at,
            "latest_health_summary": latest_health_summary,
        }

    async def set_user_active(
        self, *, admin_user_id: int, user_id: int, active: bool, reason: str | None = None
    ) -> None:
        user = await User.get_or_none(id=user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
        if user.is_admin and not active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="다른 관리자 계정은 정지할 수 없습니다.",
            )
        # 정지는 사유 필수 (감사 가치)
        if not active and not (reason and reason.strip()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="계정 정지 시 사유 입력이 필요합니다.",
            )
        prev = user.is_active
        async with in_transaction():
            user.is_active = active
            await user.save(update_fields=["is_active", "updated_at"])
            await self._log(
                admin_user_id=admin_user_id,
                action=AdminAction.USER_ACTIVATE if active else AdminAction.USER_DEACTIVATE,
                target_type=TargetType.USER,
                target_id=user_id,
                detail={"from": prev, "to": active, "reason": (reason or "").strip() or None},
            )

    async def force_verify_email(self, *, admin_user_id: int, user_id: int, reason: str | None = None) -> None:
        user = await User.get_or_none(id=user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
        if user.email_verified:
            return  # idempotent
        async with in_transaction():
            user.email_verified = True
            await user.save(update_fields=["email_verified", "updated_at"])
            await self._log(
                admin_user_id=admin_user_id,
                action=AdminAction.USER_FORCE_VERIFY_EMAIL,
                target_type=TargetType.USER,
                target_id=user_id,
                detail={"reason": (reason or "").strip() or None},
            )

    async def impersonate(self, *, admin_user_id: int, user_id: int) -> dict:
        """대상 사용자에 대한 읽기전용 view 토큰 발급 + 감사 로그.

        view 토큰: access 토큰에 readonly=True, impersonator=admin_id, 30분 만료.
        일반 API는 토큰 user_id로 조회하므로 그 사용자 화면을 그대로 보게 된다.
        쓰기는 get_request_user의 readonly 가드가 403으로 막는다.
        """
        user = await User.get_or_none(id=user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
        ttl = timedelta(minutes=30)
        token = AccessToken()
        token["user_id"] = user.id
        token["readonly"] = True
        token["impersonator"] = admin_user_id
        token.set_exp(lifetime=ttl)
        async with in_transaction():
            await self._log(
                admin_user_id=admin_user_id,
                action=AdminAction.IMPERSONATE,
                target_type=TargetType.USER,
                target_id=user_id,
                detail={"impersonator": admin_user_id},
            )
        return {
            "access_token": str(token),
            "token_type": "bearer",
            "expires_in": int(ttl.total_seconds()),
            "target": {"id": user.id, "name_masked": mask_name(user.name)},
        }

    # ── 챌린지 카탈로그 ─────────────────────────────
    async def list_challenges(self, *, limit: int, offset: int) -> tuple[int, list[Challenge]]:
        total = await Challenge.all().count()
        items = await Challenge.all().order_by("-created_at").offset(offset).limit(limit)
        return total, items

    async def create_challenge(self, *, admin_user_id: int, data: dict) -> Challenge:
        async with in_transaction():
            ch = await Challenge.create(**data)
            await self._log(
                admin_user_id=admin_user_id,
                action=AdminAction.CHALLENGE_CREATE,
                target_type=TargetType.CHALLENGE,
                target_id=ch.id,
                detail=data,
            )
        return ch

    async def update_challenge(self, *, admin_user_id: int, challenge_id: int, data: dict) -> Challenge:
        ch = await Challenge.get_or_none(id=challenge_id)
        if ch is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="챌린지를 찾을 수 없습니다.")
        changes: dict[str, Any] = {}
        for k, v in data.items():
            if v is None:
                continue
            changes[k] = {"from": getattr(ch, k), "to": v}
            setattr(ch, k, v)
        if not changes:
            return ch
        async with in_transaction():
            await ch.save()
            await self._log(
                admin_user_id=admin_user_id,
                action=AdminAction.CHALLENGE_UPDATE,
                target_type=TargetType.CHALLENGE,
                target_id=challenge_id,
                detail=changes,
            )
        return ch

    async def deactivate_challenge(self, *, admin_user_id: int, challenge_id: int, reason: str | None = None) -> None:
        ch = await Challenge.get_or_none(id=challenge_id)
        if ch is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="챌린지를 찾을 수 없습니다.")
        if not ch.is_active:
            return
        async with in_transaction():
            ch.is_active = False
            await ch.save(update_fields=["is_active"])
            await self._log(
                admin_user_id=admin_user_id,
                action=AdminAction.CHALLENGE_DEACTIVATE,
                target_type=TargetType.CHALLENGE,
                target_id=challenge_id,
                detail={"reason": (reason or "").strip() or None},
            )

    # ── 통계 ────────────────────────────────────────
    async def stats_summary(self) -> dict:
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        total_users = await User.all().count()
        active_users = await User.filter(is_active=True).count()
        email_verified = await User.filter(email_verified=True).count()
        new_7d = await User.filter(created_at__gte=week_ago).count()
        new_30d = await User.filter(created_at__gte=month_ago).count()
        total_hc = await HealthCheck.all().count()
        total_ls = await LifestyleSurvey.all().count()
        total_uc = await UserChallenge.all().count()
        total_ci = (await UserChallenge.all().values_list("total_checkins", flat=True)) or [0]
        total_checkins = sum(total_ci)
        active_catalog = await Challenge.filter(is_active=True).count()

        # CKD stage 분포 — 사용자별 최신 검진을 단일 쿼리로 집계 (PostgreSQL DISTINCT ON).
        # 이전엔 사용자 루프 + 사용자당 1쿼리(N+1) — 사용자 1000명이면 1000쿼리 → P95 위반(REQ 5-1).
        from tortoise import Tortoise

        conn = Tortoise.get_connection("default")
        _, raw = await conn.execute_query(
            """
            SELECT u.id AS user_id, latest.ckd_stage
            FROM users u
            LEFT JOIN LATERAL (
                SELECT ckd_stage
                FROM health_checks
                WHERE user_id = u.id
                ORDER BY checked_date DESC
                LIMIT 1
            ) AS latest ON true
            """
        )
        stage_dist: dict[str, int] = {"G1": 0, "G2": 0, "G3A": 0, "G3B": 0, "G4": 0, "G5": 0, "UNKNOWN": 0}
        for row in raw:
            stage_key = row.get("ckd_stage") or "UNKNOWN"
            stage_dist[stage_key] = stage_dist.get(stage_key, 0) + 1

        # 카테고리별 챌린지 카탈로그 분포 (활성만)
        _, cat_rows = await conn.execute_query(
            "SELECT category, COUNT(*) AS cnt FROM challenges WHERE is_active = true GROUP BY category"
        )
        cat_dist: dict[str, int] = {"HYDRATION": 0, "EXERCISE": 0, "DIET": 0, "SLEEP": 0, "STRESS": 0}
        for row in cat_rows:
            cat_dist[row["category"]] = row["cnt"]

        # 지난 30일 일별 신규 가입 시계열 (가입 0인 날도 0으로 채움)
        _, signup_rows = await conn.execute_query(
            """
            SELECT DATE(created_at) AS d, COUNT(*) AS cnt
            FROM users
            WHERE created_at >= $1
            GROUP BY d
            ORDER BY d
            """,
            [month_ago],
        )
        signup_map = {str(r["d"]): r["cnt"] for r in signup_rows}
        signups: list[dict] = []
        for i in range(30, -1, -1):
            d = (now - timedelta(days=i)).date()
            signups.append({"date": d.isoformat(), "count": signup_map.get(str(d), 0)})

        return {
            "total_users": total_users,
            "active_users": active_users,
            "email_verified_users": email_verified,
            "new_users_7d": new_7d,
            "new_users_30d": new_30d,
            "total_health_checks": total_hc,
            "total_lifestyle_surveys": total_ls,
            "total_user_challenges": total_uc,
            "total_checkins": total_checkins,
            "challenges_active_catalog": active_catalog,
            "ckd_stage_distribution": stage_dist,
            "challenges_by_category": cat_dist,
            "signups_last_30d": signups,
        }

    # ── 감사 로그 ────────────────────────────────────
    async def list_logs(
        self,
        *,
        limit: int,
        offset: int,
        action: AdminAction | None = None,
        target_type: TargetType | None = None,
        admin_user_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[int, list[AdminActionLog]]:
        qs = AdminActionLog.all()
        if action:
            qs = qs.filter(action=action)
        if target_type:
            qs = qs.filter(target_type=target_type)
        if admin_user_id:
            qs = qs.filter(admin_user_id=admin_user_id)
        if since:
            qs = qs.filter(created_at__gte=since)
        if until:
            qs = qs.filter(created_at__lte=until)
        total = await qs.count()
        items = await qs.order_by("-created_at").offset(offset).limit(limit)
        return total, items

    # ── 세이프티 가드 이력 ───────────────────────────
    async def list_safety_events(
        self,
        *,
        limit: int,
        offset: int,
        event_type: SafetyEventType | None = None,
        only_unacknowledged: bool = False,
    ) -> tuple[int, list[dict]]:
        qs = SafetyEvent.all()
        if event_type:
            qs = qs.filter(event_type=event_type)
        if only_unacknowledged:
            qs = qs.filter(acknowledged=False)
        total = await qs.count()
        rows = await qs.order_by("-created_at").offset(offset).limit(limit).prefetch_related("user")
        items: list[dict] = []
        for ev in rows:
            items.append(
                {
                    "id": ev.id,
                    "user_id": ev.user_id,
                    "user_email_masked": _mask_email_for_log(ev.user.email),
                    "health_check_id": ev.health_check_id,
                    "event_type": ev.event_type,
                    "value": ev.value,
                    "message": ev.message,
                    "acknowledged": ev.acknowledged,
                    "acknowledged_by": ev.acknowledged_by_id,
                    "acknowledged_at": ev.acknowledged_at,
                    "created_at": ev.created_at,
                }
            )
        return total, items

    async def acknowledge_safety_event(self, *, admin_user_id: int, event_id: int, note: str | None) -> None:
        ev = await SafetyEvent.get_or_none(id=event_id)
        if ev is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="이벤트를 찾을 수 없습니다.")
        if ev.acknowledged:
            return
        now = datetime.now(UTC)
        async with in_transaction():
            ev.acknowledged = True
            ev.acknowledged_by_id = admin_user_id
            ev.acknowledged_at = now
            await ev.save(update_fields=["acknowledged", "acknowledged_by_id", "acknowledged_at"])
            # 감사 로그에도 기록 (admin이 PHI 수치를 봤음 — 책임 추적)
            await self._log(
                admin_user_id=admin_user_id,
                action=AdminAction.SAFETY_EVENT_ACK,
                target_type=TargetType.USER,
                target_id=ev.user_id,
                detail={
                    "safety_event_id": event_id,
                    "event_type": ev.event_type,
                    "note": (note or "").strip() or None,
                },
            )

    # ── 내부 ───────────────────────────────────────
    async def _log(
        self,
        *,
        admin_user_id: int,
        action: AdminAction,
        target_type: TargetType,
        target_id: int,
        detail: dict,
    ) -> None:
        await AdminActionLog.create(
            admin_user_id=admin_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
