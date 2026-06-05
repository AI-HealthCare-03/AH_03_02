from enum import StrEnum

from tortoise import fields, models


class MicroChallengeCode(StrEnum):
    """REQ-CHAL-006 마이크로 챌린지 5종 (카테고리별 1개)."""

    HYDRATION_CUP = "HYDRATION_CUP"
    EXERCISE_STRETCH = "EXERCISE_STRETCH"
    DIET_VEGGIE = "DIET_VEGGIE"
    SLEEP_EARLY = "SLEEP_EARLY"
    STRESS_BREATH = "STRESS_BREATH"


class SlumpMicroLog(models.Model):
    """REQ-CHAL-006 슬럼프(5일 이상 미체크인) 시 제공되는 마이크로 챌린지 체크인 기록.

    일별 중복 차단을 위해 (user, micro_code, log_date) UNIQUE.
    체크인 시 User.last_checkin_date 갱신 → 슬럼프 자연 해제 + 충전 모드 진입 회피.
    """

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="slump_micro_logs", on_delete=fields.CASCADE)
    micro_code = fields.CharEnumField(enum_type=MicroChallengeCode, description="마이크로 챌린지 종류")
    log_date = fields.DateField(description="기록 일자 (일별 중복 차단)")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "slump_micro_logs"
        indexes = [("user_id", "log_date")]
        unique_together = (("user", "micro_code", "log_date"),)
