from enum import StrEnum

from tortoise import fields, models


class DrinkType(StrEnum):
    WATER = "WATER"  # 물
    COFFEE = "COFFEE"  # 커피
    JUICE = "JUICE"  # 주스
    OTHER = "OTHER"  # 기타


class WaterIntakeEntry(models.Model):
    """한 번의 수분 섭취 = 1행 (하루 복수 입력 가능)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="water_entries")
    log_date = fields.DateField(description="섭취 날짜 (YYYY-MM-DD)")
    amount_ml = fields.IntField(description="용량 (mL, 양수)")
    drink_type = fields.CharEnumField(enum_type=DrinkType, default=DrinkType.WATER)
    created_at = fields.DatetimeField(auto_now_add=True, description="섭취 시각")

    class Meta:
        table = "water_intake_entries"
        ordering = ["-created_at"]
        indexes = [("user_id", "log_date")]


class RecordSettings(models.Model):
    """사용자별 기록 설정 (확장 대비 — 이후 weight_alert_kg 등 추가)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.OneToOneField("models.User", related_name="record_settings")
    water_goal_ml = fields.IntField(null=True, description="null=미설정(트랙 기본값 사용)")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "record_settings"


class WeightLog(models.Model):
    """날짜별 1회 체중 기록 (수정 가능 = upsert)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="weight_logs")
    log_date = fields.DateField()
    weight_kg = fields.DecimalField(max_digits=4, decimal_places=1, description="체중 (kg, 소수 1자리)")
    note = fields.TextField(null=True)
    measured_at = fields.DatetimeField(auto_now=True, description="마지막 입력 시각")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "weight_logs"
        unique_together = [("user", "log_date")]
        ordering = ["-log_date"]


class SleepLog(models.Model):
    """날짜별 1회 수면 기록 (기상일 기준, 수정 가능)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="sleep_logs")
    log_date = fields.DateField(description="기상일 (전날밤 취침→오늘 기상)")
    # TimeField는 timezone 설정(Asia/Seoul) 하에서 tz-aware time이 되어 asyncpg가 거부.
    # "HH:MM" 문자열로 저장(표시 그대로, tz 무관).
    bed_time = fields.CharField(max_length=5, description="취침 시각 HH:MM")
    wake_time = fields.CharField(max_length=5, description="기상 시각 HH:MM")
    wake_count = fields.IntField(default=0, description="수면 중 깬 횟수 0~3 (3=3회 이상)")
    duration_min = fields.IntField(description="수면 시간(분) — 자정 넘김 자동 계산")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "sleep_logs"
        unique_together = [("user", "log_date")]
        ordering = ["-log_date"]
