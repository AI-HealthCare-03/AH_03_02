"""세이프티 가드 발동 이력 (의료 안전).

위험 수치 감지 시 즉시 기록 — 관리자 화면에서 모니터링.
admin 화면에서는 안전 판단을 위해 원본 수치 노출 허용 (감사 로그에 admin 액션 함께 기록).
"""

from enum import StrEnum

from tortoise import fields, models


class SafetyEventType(StrEnum):
    BP_CRISIS = "BP_CRISIS"  # 혈압 ≥180 또는 이완기 ≥120
    GLUCOSE_CRISIS = "GLUCOSE_CRISIS"  # 공복혈당 ≥400
    EGFR_CRISIS = "EGFR_CRISIS"  # eGFR <15 (G5 신부전)


class SafetyEvent(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="safety_events", on_delete=fields.CASCADE)
    health_check = fields.ForeignKeyField(
        "models.HealthCheck", related_name="safety_events", null=True, on_delete=fields.SET_NULL
    )
    event_type = fields.CharEnumField(enum_type=SafetyEventType, description="위험 유형")
    value = fields.FloatField(description="감지된 수치")
    message = fields.TextField(description="사용자에게 표시된 안내 문구")
    acknowledged = fields.BooleanField(default=False, description="관리자 확인 여부")
    acknowledged_by = fields.ForeignKeyField(
        "models.User", related_name="acknowledged_safety_events", null=True, on_delete=fields.SET_NULL
    )
    acknowledged_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "safety_events"
        indexes = [("user_id", "created_at"), ("acknowledged", "created_at")]
        ordering = ["-created_at"]
