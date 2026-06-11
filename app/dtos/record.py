from datetime import date, datetime, time

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel
from app.models.record import DrinkType


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
    bed_time: time | None
    wake_time: time | None
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
