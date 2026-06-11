from datetime import date, datetime

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
