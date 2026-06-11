from datetime import date, timedelta

from fastapi import HTTPException
from starlette import status

from app.dtos.record import (
    AddWaterRequest,
    AddWaterResponse,
    AutoCheckinResult,
    LogSleepRequest,
    LogSleepResponse,
    LogWeightRequest,
    LogWeightResponse,
    SetSettingsRequest,
    SettingsResponse,
    SleepHistoryItem,
    SleepHistoryResponse,
    SleepTodayResponse,
    WaterEntryItem,
    WaterHistoryItem,
    WaterHistoryResponse,
    WaterTodayResponse,
    WeightHistoryItem,
    WeightHistoryResponse,
    WeightTodayResponse,
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
    SleepLogRepository,
    WaterIntakeRepository,
    WeightLogRepository,
)
from app.services.challenge import ChallengeService
from app.services.record_reference import (
    SLEEP_GOAL_MIN,
    compute_sleep_minutes,
    default_goal_ml,
    goal_type_for,
    warning_level,
    weight_warning_level,
)

_DISCLAIMER = "참고용 수치이며 의료적 진단을 대체하지 않습니다. 이상 시 담당 의료진에게 연락하세요."


class RecordService:
    def __init__(self) -> None:
        self._water = WaterIntakeRepository()
        self._settings = RecordSettingsRepository()
        self._weight = WeightLogRepository()
        self._sleep = SleepLogRepository()
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

    async def _track_of(self, user_id: int) -> ChallengeTrack:
        profile = await UserChallengeProfile.get_or_none(user_id=user_id)
        return profile.track if profile else ChallengeTrack.DAILY

    async def _build_weight_today(self, user_id: int, today: date) -> WeightTodayResponse:
        track = await self._track_of(user_id)
        rec = await self._weight.get_by_date(user_id, today)
        prev = await self._weight.get_prev_before(user_id, today)
        weight = float(rec.weight_kg) if rec else None
        prev_w = float(prev.weight_kg) if prev else None
        delta = round(weight - prev_w, 1) if (weight is not None and prev_w is not None) else None
        wl = weight_warning_level(delta, track)
        return WeightTodayResponse(
            date=today,
            weight_kg=weight,
            prev_weight_kg=prev_w,
            delta_kg=delta,
            warning_level=wl,
            note=(rec.note if rec else None),
            measured_at=(rec.measured_at if rec else None),
            has_record=rec is not None,
            disclaimer=_DISCLAIMER if wl != "none" else None,
        )

    async def get_weight_today(self, user_id: int, today: date) -> WeightTodayResponse:
        return await self._build_weight_today(user_id, today)

    async def log_weight(self, user_id: int, today: date, dto: LogWeightRequest) -> LogWeightResponse:
        await self._weight.upsert(user_id, today, dto.weight_kg, dto.note)
        today_resp = await self._build_weight_today(user_id, today)
        auto = await self._maybe_auto_checkin_record(user_id, today)
        return LogWeightResponse(today=today_resp, auto_checkin=auto)

    async def _maybe_auto_checkin_category(
        self, user_id: int, today: date, category: ChallengeCategory
    ) -> AutoCheckinResult:
        """오늘 기록 시 해당 카테고리 ACTIVE 챌린지 체크인 (try/except graceful)."""
        try:
            uc = await UserChallenge.filter(
                user_id=user_id,
                status=UserChallengeStatus.ACTIVE,
                challenge__category=category,
            ).first()
            if uc is None:
                return AutoCheckinResult(performed=False, reason="no_challenge")
            if uc.last_checkin_date == today:
                return AutoCheckinResult(performed=False, reason="already_checked_in")
            await self._challenge.checkin(uc.id, user_id, today)
            return AutoCheckinResult(performed=True, reason="logged")
        except Exception:
            return AutoCheckinResult(performed=False, reason="checkin_skipped")

    async def _maybe_auto_checkin_record(self, user_id: int, today: date) -> AutoCheckinResult:
        return await self._maybe_auto_checkin_category(user_id, today, ChallengeCategory.RECORD)

    async def delete_weight(self, user_id: int, today: date) -> WeightTodayResponse:
        await self._weight.delete_by_date(user_id, today)
        return await self._build_weight_today(user_id, today)

    async def get_weight_history(self, user_id: int, today: date, days: int) -> WeightHistoryResponse:
        days = max(1, min(days, 90))
        since = today - timedelta(days=days - 1)
        rows = await self._weight.recent(user_id, since)
        items = [WeightHistoryItem(date=r.log_date, weight_kg=float(r.weight_kg)) for r in rows]
        return WeightHistoryResponse(days=days, items=items)

    # ── 수면 기록 ────────────────────────────────────────────────────────────

    async def _build_sleep_today(self, user_id: int, today: date) -> SleepTodayResponse:
        rec = await self._sleep.get_by_date(user_id, today)
        return SleepTodayResponse(
            date=today,
            bed_time=(rec.bed_time if rec else None),
            wake_time=(rec.wake_time if rec else None),
            wake_count=(rec.wake_count if rec else None),
            duration_min=(rec.duration_min if rec else None),
            goal_met=(rec is not None and rec.duration_min >= SLEEP_GOAL_MIN),
            has_record=rec is not None,
        )

    async def get_sleep_today(self, user_id: int, today: date) -> SleepTodayResponse:
        return await self._build_sleep_today(user_id, today)

    async def log_sleep(self, user_id: int, today: date, dto: LogSleepRequest) -> LogSleepResponse:
        duration = compute_sleep_minutes(dto.bed_time, dto.wake_time)
        await self._sleep.upsert(user_id, today, dto.bed_time, dto.wake_time, dto.wake_count, duration)
        today_resp = await self._build_sleep_today(user_id, today)
        auto = await self._maybe_auto_checkin_category(user_id, today, ChallengeCategory.SLEEP)
        return LogSleepResponse(today=today_resp, auto_checkin=auto)

    async def delete_sleep(self, user_id: int, today: date) -> SleepTodayResponse:
        await self._sleep.delete_by_date(user_id, today)
        return await self._build_sleep_today(user_id, today)

    async def get_sleep_history(self, user_id: int, today: date, days: int) -> SleepHistoryResponse:
        days = max(1, min(days, 30))
        since = today - timedelta(days=days - 1)
        rows = await self._sleep.recent(user_id, since)
        items = [SleepHistoryItem(date=r.log_date, duration_min=r.duration_min) for r in rows]
        return SleepHistoryResponse(days=days, items=items)
