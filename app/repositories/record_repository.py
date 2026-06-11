from datetime import date

from tortoise.functions import Sum

from app.models.record import DrinkType, RecordSettings, WaterIntakeEntry


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
