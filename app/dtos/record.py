from datetime import date, datetime, time

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel
from app.models.record import DrinkType, ExerciseType, StressEmotion


class AddWaterRequest(BaseModel):
    amount_ml: int = Field(gt=0, le=5000, description="용량 mL (양수, 1회 5000 이하)")
    drink_type: DrinkType = DrinkType.WATER


class SetSettingsRequest(BaseModel):
    water_goal_ml: int = Field(gt=0, le=10000)


class WaterEntryItem(BaseSerializerModel):
    id: int
    amount_ml: int
    drink_type: DrinkType
    created_at: datetime


class WaterTodayResponse(BaseSerializerModel):
    date: date
    total_ml: int
    goal_ml: int
    goal_type: str  # "target" | "limit"
    progress_pct: int
    warning_level: str  # "none" | "warn" | "over"
    entries: list[WaterEntryItem]
    disclaimer: str | None = None


class AutoCheckinResult(BaseSerializerModel):
    performed: bool
    reason: str


class AddWaterResponse(BaseSerializerModel):
    today: WaterTodayResponse
    auto_checkin: AutoCheckinResult


class WaterHistoryItem(BaseSerializerModel):
    date: date
    total_ml: int


class WaterHistoryResponse(BaseSerializerModel):
    days: int
    items: list[WaterHistoryItem]


class SettingsResponse(BaseSerializerModel):
    water_goal_ml: int
    goal_type: str


class LogWeightRequest(BaseModel):
    weight_kg: float = Field(gt=20, le=300, description="체중 kg (소수 1자리)")
    note: str | None = None


class WeightTodayResponse(BaseSerializerModel):
    date: date
    weight_kg: float | None
    prev_weight_kg: float | None
    delta_kg: float | None
    warning_level: str  # "none" | "warn" | "over"
    note: str | None
    measured_at: datetime | None
    has_record: bool
    disclaimer: str | None = None


class LogWeightResponse(BaseSerializerModel):
    today: WeightTodayResponse
    auto_checkin: AutoCheckinResult


class WeightHistoryItem(BaseSerializerModel):
    date: date
    weight_kg: float


class WeightHistoryResponse(BaseSerializerModel):
    days: int
    items: list[WeightHistoryItem]


class LogSleepRequest(BaseModel):
    bed_time: time
    wake_time: time
    wake_count: int = Field(default=0, ge=0, le=3, description="0~3 (3=3회 이상)")


class SleepTodayResponse(BaseSerializerModel):
    date: date
    bed_time: str | None  # "HH:MM" (DB는 문자열 저장)
    wake_time: str | None  # "HH:MM"
    wake_count: int | None
    duration_min: int | None
    goal_met: bool
    has_record: bool


class LogSleepResponse(BaseSerializerModel):
    today: SleepTodayResponse
    auto_checkin: AutoCheckinResult


class SleepHistoryItem(BaseSerializerModel):
    date: date
    duration_min: int


class SleepHistoryResponse(BaseSerializerModel):
    days: int
    items: list[SleepHistoryItem]


class DropStressRequest(BaseModel):
    emotions: list[StressEmotion] = Field(min_length=1, description="감정 태그(1개 이상, 복수 선택)")
    # text는 받지 않음(저장 안 함 — 프론트 전용 '버리기')


class StressTodayResponse(BaseSerializerModel):
    date: date
    has_record: bool
    drop_count: int  # 오늘 '버리기' 횟수
    today_emotions: list[str]  # 오늘 누른 감정 태그 합집합(정렬)


class DropStressResponse(BaseSerializerModel):
    today: StressTodayResponse
    auto_checkin: AutoCheckinResult


class StressEmotionCount(BaseSerializerModel):
    emotion: str
    count: int


class StressHistoryResponse(BaseSerializerModel):
    days: int
    counts: list[StressEmotionCount]


class LogExerciseRequest(BaseModel):
    exercise_type: ExerciseType
    duration_min: int = Field(gt=0, le=600, description="운동 시간(분)")
    fatigue_level: int = Field(ge=1, le=5, description="주관적 피로도 1~5")
    note: str | None = None


class ExerciseEntryItem(BaseSerializerModel):
    id: int
    exercise_type: ExerciseType
    duration_min: int
    fatigue_level: int
    note: str | None
    created_at: datetime


class ExerciseTodayResponse(BaseSerializerModel):
    date: date
    entries: list[ExerciseEntryItem]
    total_duration_min: int
    max_fatigue: int | None
    has_record: bool
    suggest_rest: bool
    rest_message: str | None = None


class LogExerciseResponse(BaseSerializerModel):
    today: ExerciseTodayResponse
    auto_checkin: AutoCheckinResult


class ExerciseHistoryItem(BaseSerializerModel):
    date: date
    avg_fatigue: float


class ExerciseHistoryResponse(BaseSerializerModel):
    days: int
    items: list[ExerciseHistoryItem]
