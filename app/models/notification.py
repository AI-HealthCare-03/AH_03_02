from enum import StrEnum

from tortoise import fields, models


class NotificationType(StrEnum):
    CHALLENGE_JOINED = "CHALLENGE_JOINED"
    CHECKIN_DONE = "CHECKIN_DONE"
    CHALLENGE_COMPLETED = "CHALLENGE_COMPLETED"
    CHALLENGE_REMINDER = "CHALLENGE_REMINDER"
    EGG_GOAL_70 = "EGG_GOAL_70"
    EGG_GOAL_90 = "EGG_GOAL_90"
    EGG_HATCHED = "EGG_HATCHED"
    STAGE_BONUS = "STAGE_BONUS"
    CHARGE_MODE_IN = "CHARGE_MODE_IN"
    CHARGE_MODE_OUT = "CHARGE_MODE_OUT"
    SLUMP_RECOVERED = "SLUMP_RECOVERED"


class Notification(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="notifications")
    type = fields.CharEnumField(enum_type=NotificationType)
    title = fields.CharField(max_length=100)
    message = fields.TextField()
    is_read = fields.BooleanField(default=False)
    related_id = fields.BigIntField(null=True, description="관련 리소스 ID (user_challenge_id 등)")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "notifications"
        ordering = ["-created_at"]
