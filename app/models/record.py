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
