from datetime import date
from decimal import Decimal

from tortoise.functions import Sum

from app.models.record import DrinkType, RecordSettings, SleepLog, WaterIntakeEntry, WeightLog


class WaterIntakeRepository:
    async def add(self, user_id: int, log_date: date, amount_ml: int, drink_type: DrinkType) -> WaterIntakeEntry:
        return await WaterIntakeEntry.create(
            user_id=user_id,
            log_date=log_date,
            amount_ml=amount_ml,
            drink_type=drink_type,
        )

    async def delete(self, entry_id: int, user_id: int) -> bool:
        """소유권 필터: 본인 entry만 삭제. 삭제된 행 수>0 이면 True."""
        deleted = await WaterIntakeEntry.filter(id=entry_id, user_id=user_id).delete()
        return deleted > 0

    async def list_by_date(self, user_id: int, log_date: date) -> list[WaterIntakeEntry]:
        return await WaterIntakeEntry.filter(user_id=user_id, log_date=log_date).order_by("created_at")

    async def history(self, user_id: int, since: date) -> dict[date, int]:
        """since 이후 일별 누적량 {log_date: total_ml}."""
        rows = (
            await WaterIntakeEntry.filter(user_id=user_id, log_date__gte=since)
            .annotate(total=Sum("amount_ml"))
            .group_by("log_date")
            .values("log_date", "total")
        )
        return {r["log_date"]: int(r["total"] or 0) for r in rows}


class RecordSettingsRepository:
    async def get(self, user_id: int) -> RecordSettings | None:
        return await RecordSettings.get_or_none(user_id=user_id)

    async def upsert(self, user_id: int, water_goal_ml: int) -> RecordSettings:
        obj = await RecordSettings.get_or_none(user_id=user_id)
        if obj is None:
            return await RecordSettings.create(user_id=user_id, water_goal_ml=water_goal_ml)
        obj.water_goal_ml = water_goal_ml
        await obj.save()
        return obj


class WeightLogRepository:
    async def upsert(self, user_id: int, log_date: date, weight_kg: float, note: str | None) -> WeightLog:
        """날짜별 1행 upsert (있으면 수정). weight_kg 은 소수 1자리로 양자화."""
        value = Decimal(str(weight_kg)).quantize(Decimal("0.1"))
        obj = await WeightLog.get_or_none(user_id=user_id, log_date=log_date)
        if obj is None:
            return await WeightLog.create(user_id=user_id, log_date=log_date, weight_kg=value, note=note)
        obj.weight_kg = value
        obj.note = note
        await obj.save()
        return obj

    async def get_by_date(self, user_id: int, log_date: date) -> WeightLog | None:
        return await WeightLog.get_or_none(user_id=user_id, log_date=log_date)

    async def get_prev_before(self, user_id: int, log_date: date) -> WeightLog | None:
        """log_date 직전(이전 날짜)의 최신 기록 — '어제 대비' 비교용(공백 허용)."""
        return await WeightLog.filter(user_id=user_id, log_date__lt=log_date).order_by("-log_date").first()

    async def delete_by_date(self, user_id: int, log_date: date) -> bool:
        deleted = await WeightLog.filter(user_id=user_id, log_date=log_date).delete()
        return deleted > 0

    async def recent(self, user_id: int, since: date) -> list[WeightLog]:
        return await WeightLog.filter(user_id=user_id, log_date__gte=since).order_by("log_date")


class SleepLogRepository:
    async def upsert(self, user_id: int, log_date, bed_time, wake_time, wake_count: int, duration_min: int) -> SleepLog:
        obj = await SleepLog.get_or_none(user_id=user_id, log_date=log_date)
        if obj is None:
            return await SleepLog.create(
                user_id=user_id,
                log_date=log_date,
                bed_time=bed_time,
                wake_time=wake_time,
                wake_count=wake_count,
                duration_min=duration_min,
            )
        obj.bed_time = bed_time
        obj.wake_time = wake_time
        obj.wake_count = wake_count
        obj.duration_min = duration_min
        await obj.save()
        return obj

    async def get_by_date(self, user_id: int, log_date) -> SleepLog | None:
        return await SleepLog.get_or_none(user_id=user_id, log_date=log_date)

    async def delete_by_date(self, user_id: int, log_date) -> bool:
        deleted = await SleepLog.filter(user_id=user_id, log_date=log_date).delete()
        return deleted > 0

    async def recent(self, user_id: int, since) -> list[SleepLog]:
        return await SleepLog.filter(user_id=user_id, log_date__gte=since).order_by("log_date")
