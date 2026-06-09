from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.dtos.base import BaseSerializerModel
from app.models.gamification import CharacterSpecies, ItemCode


class EggResponse(BaseSerializerModel):
    egg_no: int
    progress_checkins: int
    current_stage: int
    progress_percent: int  # progress_checkins / 100 * 100
    goal_70_alerted: bool
    goal_90_alerted: bool
    is_legendary: bool | None
    species: CharacterSpecies | None
    character_name: str | None
    started_at: datetime


class EggHistoryItem(BaseSerializerModel):
    egg_no: int
    is_legendary: bool | None
    species: CharacterSpecies | None
    character_name: str | None
    started_at: datetime
    hatched_at: datetime


class CharacterRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)

    @field_validator("name")
    @classmethod
    def _strip_not_empty(cls, v: str) -> str:
        # min_length=1은 공백만("   ")도 통과시키므로 strip 후 비어있지 않음을 강제
        stripped = v.strip()
        if not stripped:
            raise ValueError("이름은 공백일 수 없습니다.")
        return stripped


class SkinEquipRequest(BaseModel):
    item_code: ItemCode | None = Field(None, description="장착할 스킨 코드. null이면 해제(기본 외형).")


class SkinEquipResponse(BaseSerializerModel):
    active_skin_code: ItemCode | None


class EggHistoryResponse(BaseSerializerModel):
    total: int
    legendary_count: int
    items: list[EggHistoryItem]


class ChargeModeResponse(BaseSerializerModel):
    is_active: bool
    entered_at: datetime | None
    exited_at: datetime | None
    days_since_last_checkin: int | None
    warning_4d_alerted: bool
    warning_5d_alerted: bool
    warning_6d_alerted: bool


class InventoryItem(BaseSerializerModel):
    item_code: ItemCode
    quantity: int
    acquired_at: datetime


class InventoryResponse(BaseSerializerModel):
    total: int
    items: list[InventoryItem]


class MascotResponse(BaseSerializerModel):
    current_egg: EggResponse
    charge_mode: ChargeModeResponse
    legendary_unlocked: bool  # 부화 이력 중 전설 한 번이라도?
    skin_active: ItemCode | None  # 보유 스킨 중 가장 비싼 거 (단순화)
    proficiency: int  # 챌린지 숙련도 1~4 (EggWidget 배경 결정용)
    max_stage_ever: int = 0  # 모든 알 중 누적 최고 진화 단계 (0~3) — 동물 스킨 잠금 판단
