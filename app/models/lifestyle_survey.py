from enum import StrEnum

from tortoise import fields, models

from app.models.health_check import DialysisType


class SmokingStatus(StrEnum):
    NEVER = "NEVER"
    PAST = "PAST"
    CURRENT = "CURRENT"


class DrinkingFrequency(StrEnum):
    NEVER = "NEVER"
    OCCASIONALLY = "OCCASIONALLY"
    WEEKLY = "WEEKLY"
    DAILY = "DAILY"


class StressLevel(StrEnum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class MaritalStatus(StrEnum):
    """결혼 여부 (REQ-DATA-006)."""

    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"
    OTHER = "OTHER"


class LifestyleSurvey(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="lifestyle_surveys")
    surveyed_date = fields.DateField(description="설문 응답일")

    # 흡연·음주·운동·수면·수분·스트레스 (기존)
    smoking_status = fields.CharEnumField(enum_type=SmokingStatus, description="흡연 상태")
    drinking_frequency = fields.CharEnumField(enum_type=DrinkingFrequency, description="음주 빈도")
    exercise_days_per_week = fields.IntField(description="주당 운동 일수 (0~7)")
    sleep_hours_per_day = fields.FloatField(null=True, description="하루 평균 수면 시간 (시간)")
    daily_water_intake = fields.FloatField(null=True, description="하루 평균 수분 섭취량 (L)")
    stress_level = fields.CharEnumField(enum_type=StressLevel, null=True, description="스트레스 수준")

    # REQ-DATA-006 신규 — 운동 강도·시간 (KNHANES 변수와 매핑)
    vigorous_exercise_days = fields.IntField(default=0, description="주당 고강도 신체활동 일수 (0~7)")
    vigorous_exercise_minutes = fields.IntField(default=0, description="고강도 활동 하루 평균 분")
    moderate_exercise_days = fields.IntField(default=0, description="주당 중강도 신체활동 일수 (0~7)")
    moderate_exercise_minutes = fields.IntField(default=0, description="중강도 활동 하루 평균 분")
    sitting_hours_per_day = fields.FloatField(null=True, description="하루 좌식 시간 (시간)")

    # REQ-DATA-006 신규 — 결혼 여부
    marital_status = fields.CharEnumField(enum_type=MaritalStatus, null=True, description="결혼 여부")

    # REQ-DATA-006 신규 — 가족력 3종 (당뇨·고혈압·심장질환)
    family_history_diabetes = fields.BooleanField(default=False, description="가족력: 당뇨")
    family_history_hypertension = fields.BooleanField(default=False, description="가족력: 고혈압")
    family_history_heart_disease = fields.BooleanField(default=False, description="가족력: 심장질환")
    family_history_dyslipidemia = fields.BooleanField(default=False, description="가족력: 이상지질혈증")
    family_history_stroke = fields.BooleanField(default=False, description="가족력: 뇌졸중")

    # 본인 진단력 — htn/dm_diagnosed는 모델 입력(ckd_label 상관 높음), ckd_diagnosed는 케어 분기용(정책)
    htn_diagnosed = fields.BooleanField(default=False, description="본인 고혈압 진단")
    dm_diagnosed = fields.BooleanField(default=False, description="본인 당뇨 진단")
    dyslipidemia_diagnosed = fields.BooleanField(default=False, description="본인 이상지질혈증 진단")
    ckd_diagnosed = fields.BooleanField(
        default=False, description="본인 만성콩팥병(CKD) 진단 — True 시 챌린지 대신 주치의 지시 안내"
    )
    dialysis_type = fields.CharEnumField(
        enum_type=DialysisType,
        null=True,
        description="투석 종류 (CKD 진단자만, null=미진단/미입력) — 챌린지 트랙·app_group 판정용",
    )

    # 임신 여부 — 임신 중에는 신장 수치·정상 범위 해석이 일반과 달라 본 선별 결과를 그대로 적용하기 어려움.
    # 대시보드 상단 안전 안내 배너 노출용 (산부인과·주치의 상담 권고).
    is_pregnant = fields.BooleanField(default=False, description="임신 여부 (체크 시 대시보드 안전 안내 노출)")

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "lifestyle_surveys"
        ordering = ["-surveyed_date"]
