from datetime import date, timedelta

from fastapi import HTTPException
from starlette import status

from app.dtos.record import (
    AddWaterRequest,
    AddWaterResponse,
    AutoCheckinResult,
    SetSettingsRequest,
    SettingsResponse,
    WaterEntryItem,
    WaterHistoryItem,
    WaterHistoryResponse,
    WaterTodayResponse,
)
from app.models.challenge import (
    ChallengeCategory,
    ChallengeTrack,
    UserChallenge,
    UserChallengeProfile,
    UserChallengeStatus,
)
from app.repositories.record_repository import (
    RecordSettingsRepository,
    WaterIntakeRepository,
)
from app.services.challenge import ChallengeService
from app.services.record_reference import default_goal_ml, goal_type_for, warning_level

_DISCLAIMER = "참고용 수치이며 의료적 진단을 대체하지 않습니다. 이상 시 담당 의료진에게 연락하세요."


class RecordService:
    def __init__(self) -> None:
        self._water = WaterIntakeRepository()
        self._settings = RecordSettingsRepository()
        self._challenge = ChallengeService()

    async def _resolve_goal(self, user_id: int) -> tuple[int, str]:
        """(goal_ml, goal_type) 반환. 설정 없으면 트랙 기본값. 프로필 없으면 DAILY(달성형)."""
        profile = await UserChallengeProfile.get_or_none(user_id=user_id)
        track = profile.track if profile else ChallengeTrack.DAILY
        gtype = goal_type_for(track)
        settings = await self._settings.get(user_id)
        goal = settings.water_goal_ml if settings and settings.water_goal_ml else default_goal_ml(track)
        return goal, gtype

    async def _build_today(self, user_id: int, today: date) -> WaterTodayResponse:
        goal, gtype = await self._resolve_goal(user_id)
        entries = await self._water.list_by_date(user_id, today)
        total = sum(e.amount_ml for e in entries)
        wl = warning_level(total, goal, gtype)
        pct = round(total / goal * 100) if goal else 0
        return WaterTodayResponse(
            date=today,
            total_ml=total,
            goal_ml=goal,
            goal_type=gtype,
            progress_pct=pct,
            warning_level=wl,
            entries=[WaterEntryItem.model_validate(e) for e in entries],
            disclaimer=_DISCLAIMER if (gtype == "limit" and wl != "none") else None,
        )

    async def get_today(self, user_id: int, today: date) -> WaterTodayResponse:
        return await self._build_today(user_id, today)

    async def add_water(self, user_id: int, today: date, dto: AddWaterRequest) -> AddWaterResponse:
        await self._water.add(user_id, today, dto.amount_ml, dto.drink_type)
        today_resp = await self._build_today(user_id, today)
        auto = await self._maybe_auto_checkin(user_id, today, today_resp)
        return AddWaterResponse(today=today_resp, auto_checkin=auto)

    async def _maybe_auto_checkin(self, user_id: int, today: date, today_resp: WaterTodayResponse) -> AutoCheckinResult:
        """달성형 + 목표도달 시에만 ACTIVE HYDRATION 챌린지 체크인.

        전체를 try/except로 감싸 체크인 실패해도 수분 기록은 성공 유지.
        """
        try:
            if today_resp.goal_type != "target" or today_resp.total_ml < today_resp.goal_ml:
                return AutoCheckinResult(performed=False, reason="not_target_or_below_goal")
            uc = await UserChallenge.filter(
                user_id=user_id,
                status=UserChallengeStatus.ACTIVE,
                challenge__category=ChallengeCategory.HYDRATION,
            ).first()
            if uc is None:
                return AutoCheckinResult(performed=False, reason="no_hydration_challenge")
            if uc.last_checkin_date == today:
                return AutoCheckinResult(performed=False, reason="already_checked_in")
            await self._challenge.checkin(uc.id, user_id, today)
            return AutoCheckinResult(performed=True, reason="goal_reached")
        except Exception:
            return AutoCheckinResult(performed=False, reason="checkin_skipped")

    async def delete_water(self, user_id: int, today: date, entry_id: int) -> WaterTodayResponse:
        ok = await self._water.delete(entry_id, user_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
        return await self._build_today(user_id, today)

    async def get_history(self, user_id: int, today: date, days: int) -> WaterHistoryResponse:
        days = max(1, min(days, 90))
        since = today - timedelta(days=days - 1)
        agg = await self._water.history(user_id, since)
        items = [WaterHistoryItem(date=d, total_ml=t) for d, t in sorted(agg.items())]
        return WaterHistoryResponse(days=days, items=items)

    async def get_settings(self, user_id: int) -> SettingsResponse:
        goal, gtype = await self._resolve_goal(user_id)
        return SettingsResponse(water_goal_ml=goal, goal_type=gtype)

    async def set_settings(self, user_id: int, dto: SetSettingsRequest) -> SettingsResponse:
        await self._settings.upsert(user_id, dto.water_goal_ml)
        return await self.get_settings(user_id)
