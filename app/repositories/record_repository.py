from datetime import date
from decimal import Decimal

from tortoise.functions import Avg, Sum

from app.models.record import (
    Appointment,
    DrinkType,
    ExerciseLog,
    LabRecord,
    RecordSettings,
    SleepLog,
    StressLog,
    UserLabMetrics,
    WaterIntakeEntry,
    WeightLog,
)


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


class StressLogRepository:
    async def add(self, user_id: int, log_date: date, emotions: list[str]) -> StressLog:
        return await StressLog.create(user_id=user_id, log_date=log_date, emotions=emotions)

    async def list_by_date(self, user_id: int, log_date: date) -> list[StressLog]:
        return await StressLog.filter(user_id=user_id, log_date=log_date).order_by("created_at")

    async def recent(self, user_id: int, since: date) -> list[StressLog]:
        """since 이후 모든 행(7일 빈도 집계용, 정렬 무관)."""
        return await StressLog.filter(user_id=user_id, log_date__gte=since)


class ExerciseLogRepository:
    async def add(
        self,
        user_id: int,
        log_date: date,
        exercise_type: str,
        duration_min: int,
        fatigue_level: int,
        note: str | None,
    ) -> ExerciseLog:
        return await ExerciseLog.create(
            user_id=user_id,
            log_date=log_date,
            exercise_type=exercise_type,
            duration_min=duration_min,
            fatigue_level=fatigue_level,
            note=note,
        )

    async def list_by_date(self, user_id: int, log_date: date) -> list[ExerciseLog]:
        return await ExerciseLog.filter(user_id=user_id, log_date=log_date).order_by("created_at")

    async def daily_avg_fatigue(self, user_id: int, since: date) -> dict[date, float]:
        """since 이후 일별 평균 피로도 {log_date: avg_fatigue}."""
        rows = (
            await ExerciseLog.filter(user_id=user_id, log_date__gte=since)
            .annotate(avg=Avg("fatigue_level"))
            .group_by("log_date")
            .values("log_date", "avg")
        )
        return {r["log_date"]: float(r["avg"] or 0) for r in rows}

    async def delete(self, entry_id: int, user_id: int) -> bool:
        """소유권 필터: 본인 entry만 삭제. 삭제된 행 수>0 이면 True."""
        deleted = await ExerciseLog.filter(id=entry_id, user_id=user_id).delete()
        return deleted > 0


class LabRecordRepository:
    async def upsert(self, user_id: int, measured_date: date, values: dict) -> LabRecord:
        obj = await LabRecord.get_or_none(user_id=user_id, measured_date=measured_date)
        if obj is None:
            return await LabRecord.create(user_id=user_id, measured_date=measured_date, values=values)
        # 같은 날짜 재저장 시 기존 지표값과 병합(부분 저장이 이전 키를 지우지 않게)
        obj.values = {**(obj.values or {}), **values}
        await obj.save()
        return obj

    async def get_by_date(self, user_id: int, measured_date: date) -> LabRecord | None:
        return await LabRecord.get_or_none(user_id=user_id, measured_date=measured_date)

    async def recent(self, user_id: int, limit: int) -> list[LabRecord]:
        """measured_date 내림차순 최근 limit개 (추세용)."""
        return await LabRecord.filter(user_id=user_id).order_by("-measured_date").limit(limit)

    async def delete_by_date(self, user_id: int, measured_date: date) -> bool:
        deleted = await LabRecord.filter(user_id=user_id, measured_date=measured_date).delete()
        return deleted > 0


class UserLabMetricsRepository:
    async def get(self, user_id: int) -> UserLabMetrics | None:
        return await UserLabMetrics.get_or_none(user_id=user_id)

    async def upsert(self, user_id: int, metric_keys: list[str]) -> UserLabMetrics:
        obj = await UserLabMetrics.get_or_none(user_id=user_id)
        if obj is None:
            return await UserLabMetrics.create(user_id=user_id, metric_keys=metric_keys)
        obj.metric_keys = metric_keys
        await obj.save()
        return obj


class AppointmentRepository:
    async def create(
        self,
        user_id: int,
        appt_date: date,
        appt_time: str | None,
        appt_type: str,
        hospital: str | None,
        note: str | None,
    ) -> Appointment:
        return await Appointment.create(
            user_id=user_id,
            appt_date=appt_date,
            appt_time=appt_time,
            appt_type=appt_type,
            hospital=hospital,
            note=note,
        )

    async def list_between(self, user_id: int, start: date, end: date) -> list[Appointment]:
        return await Appointment.filter(user_id=user_id, appt_date__gte=start, appt_date__lte=end).order_by(
            "appt_date", "appt_time"
        )

    async def upcoming(self, user_id: int, today: date, limit: int) -> list[Appointment]:
        return (
            await Appointment.filter(user_id=user_id, appt_date__gte=today)
            .order_by("appt_date", "appt_time")
            .limit(limit)
        )

    async def past(self, user_id: int, today: date, limit: int) -> list[Appointment]:
        return (
            await Appointment.filter(user_id=user_id, appt_date__lt=today)
            .order_by("-appt_date", "-appt_time")
            .limit(limit)
        )

    async def get(self, appt_id: int, user_id: int) -> Appointment | None:
        return await Appointment.get_or_none(id=appt_id, user_id=user_id)

    async def update(self, appt_id: int, user_id: int, data: dict) -> Appointment | None:
        obj = await Appointment.get_or_none(id=appt_id, user_id=user_id)
        if obj is None:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        await obj.save()
        return obj

    async def delete(self, appt_id: int, user_id: int) -> bool:
        deleted = await Appointment.filter(id=appt_id, user_id=user_id).delete()
        return deleted > 0
