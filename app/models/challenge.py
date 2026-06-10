from enum import StrEnum

from tortoise import fields, models


class ChallengeCategory(StrEnum):
    HYDRATION = "HYDRATION"  # 수분
    EXERCISE = "EXERCISE"  # 운동 (전 트랙 공유)
    DIET = "DIET"  # 식단
    SLEEP = "SLEEP"  # 수면
    STRESS = "STRESS"  # 스트레스
    EDUCATION = "EDUCATION"  # 교육·이해 (투석/CKD)
    RECORD = "RECORD"  # 기록 습관 (투석/CKD)
    MONITORING = "MONITORING"  # 검사·수치 관리 (투석/CKD)
    EMOTION = "EMOTION"  # 정서 (투석/CKD)


class ChallengeTrack(StrEnum):
    DIALYSIS = "DIALYSIS"  # 투석·이식 트랙 (CKD진단 + 투석/이식 or eGFR<15)
    CKD = "CKD"  # 비투석 CKD 트랙 (CKD진단 보존기)
    INTENSIVE = "INTENSIVE"  # 집중케어 트랙 (A그룹)
    DAILY = "DAILY"  # 일상케어 트랙 (B·C그룹)
    WELLNESS = "WELLNESS"  # 웰니스 트랙 (D그룹)


class UserChallengeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class CheckinEmotion(StrEnum):
    """체크인 시 감정 7종 (REQ-DASH-001 ⑤)."""

    VERY_HAPPY = "VERY_HAPPY"  # 😄
    HAPPY = "HAPPY"  # 🙂
    NEUTRAL = "NEUTRAL"  # 😐
    ANXIOUS = "ANXIOUS"  # 😟
    SAD = "SAD"  # 😢
    ANGRY = "ANGRY"  # 😠
    TIRED = "TIRED"  # 😴


class Challenge(models.Model):
    id = fields.BigIntField(primary_key=True)
    name = fields.CharField(max_length=200)
    category = fields.CharEnumField(enum_type=ChallengeCategory)
    description = fields.TextField()
    duration_days = fields.IntField(description="챌린지 총 기간 (일)")
    track = fields.CharEnumField(enum_type=ChallengeTrack)
    stage = fields.IntField(default=1, description="난이도 단계 1=입문 2=초보 3=중급 4=숙련")
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "challenges"
        ordering = ["track", "stage", "category"]


class UserChallenge(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="user_challenges")
    challenge = fields.ForeignKeyField("models.Challenge", related_name="participants")
    started_at = fields.DateField(description="챌린지 시작일")
    status = fields.CharEnumField(enum_type=UserChallengeStatus, default=UserChallengeStatus.ACTIVE)
    streak_count = fields.IntField(default=0, description="연속 체크인 일수")
    total_checkins = fields.IntField(default=0, description="누적 체크인 횟수")
    last_checkin_date = fields.DateField(null=True, description="마지막 체크인 날짜")
    last_emotion = fields.CharEnumField(enum_type=CheckinEmotion, null=True, description="가장 최근 체크인 감정")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_challenges"
        unique_together = [("user", "challenge")]


class CheckinEmotionLog(models.Model):
    """일별 체크인 감정 기록 (주간 듀얼 축 차트용)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="emotion_logs")
    log_date = fields.DateField()
    emotion = fields.CharEnumField(enum_type=CheckinEmotion)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "checkin_emotion_logs"
        ordering = ["-log_date"]


class DailyChecklistLog(models.Model):
    """매일 필수 체크리스트 일별 기록 (트랙별 고정 항목)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="daily_checklist_logs")
    log_date = fields.DateField()
    item_key = fields.CharField(
        max_length=40,
        description="medication/diet_fluid/appointment/symptom 등",
    )
    checked = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "daily_checklist_logs"
        unique_together = [("user", "log_date", "item_key")]


class UserChallengeProfile(models.Model):
    """사용자별 챌린지 트랙/스테이지 선택 (자동배정 결과 저장 + 수동변경)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.OneToOneField("models.User", related_name="challenge_profile")
    track = fields.CharEnumField(enum_type=ChallengeTrack)
    stage = fields.IntField(default=1, description="1~4")
    auto_assigned = fields.BooleanField(
        default=True,
        description="자동배정 후 사용자 변경 시 False",
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_challenge_profiles"
