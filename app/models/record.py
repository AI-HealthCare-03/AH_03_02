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


class StressEmotion(StrEnum):
    """감정 쓰레기통 전용 감정 태그 8종 (체크인용 CheckinEmotion 7종과 별개)."""

    ANXIOUS = "ANXIOUS"  # 불안
    TENSE = "TENSE"  # 긴장
    ANGRY = "ANGRY"  # 화남
    SAD = "SAD"  # 슬픔
    LONELY = "LONELY"  # 외로움
    LISTLESS = "LISTLESS"  # 무기력
    GRATEFUL = "GRATEFUL"  # 감사
    RELIEVED = "RELIEVED"  # 안도


class StressLog(models.Model):
    """'감정 쓰레기통' 1회 = 1행 (하루 복수 가능). 버린 텍스트는 저장 안 함."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="stress_logs")
    log_date = fields.DateField(description="감정 버린 날짜")
    emotions = fields.JSONField(description="선택한 감정 태그 값 list[str] (StressEmotion)")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "stress_logs"
        ordering = ["-created_at"]
        indexes = [("user_id", "log_date")]


class ExerciseType(StrEnum):
    """운동 종류 5종."""

    WALK = "WALK"  # 걷기
    CYCLE = "CYCLE"  # 자전거
    STRENGTH = "STRENGTH"  # 근력
    STRETCH = "STRETCH"  # 스트레칭
    OTHER = "OTHER"  # 기타


class ExerciseLog(models.Model):
    """'운동 1회 = 1행' (하루 복수 가능). 주관적 피로도 1~5."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="exercise_logs")
    log_date = fields.DateField(description="운동 날짜")
    exercise_type = fields.CharEnumField(enum_type=ExerciseType)
    duration_min = fields.IntField(description="운동 시간(분)")
    fatigue_level = fields.IntField(description="주관적 피로도 1~5")
    note = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "exercise_logs"
        ordering = ["-created_at"]
        indexes = [("user_id", "log_date")]


class LabRecord(models.Model):
    """검사 1회(날짜) = 1행. 검사일별 지표값 dict, 수정 가능(upsert)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="lab_records")
    measured_date = fields.DateField(description="검사일")
    values = fields.JSONField(description="입력한 지표값 {metric_key: float}")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "lab_records"
        unique_together = [("user", "measured_date")]
        ordering = ["-measured_date"]


class UserLabMetrics(models.Model):
    """사용자가 추적할 지표 키 목록(커스텀). 없으면 트랙 기본 지표 사용."""

    id = fields.BigIntField(primary_key=True)
    user = fields.OneToOneField("models.User", related_name="lab_metrics")
    metric_keys = fields.JSONField(description="활성 지표 키 list[str]")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_lab_metrics"


class AppointmentType(StrEnum):
    """진료 일정 종류 4종."""

    CHECKUP = "CHECKUP"  # 정기 진료
    DIALYSIS = "DIALYSIS"  # 투석
    BLOOD_TEST = "BLOOD_TEST"  # 혈액검사
    OTHER = "OTHER"  # 기타


class Appointment(models.Model):
    """진료 일정 1건 = 1행 (하루 복수 가능)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="appointments")
    appt_date = fields.DateField(description="진료일")
    appt_time = fields.CharField(max_length=5, null=True, description="시각 HH:MM(선택)")
    appt_type = fields.CharEnumField(enum_type=AppointmentType)
    hospital = fields.CharField(max_length=100, null=True)
    note = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "appointments"
        indexes = [("user_id", "appt_date")]
        ordering = ["appt_date", "appt_time"]
