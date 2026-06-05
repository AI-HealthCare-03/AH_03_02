from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.slump import MicroChallengeCode


class MicroChallengeDTO(BaseModel):
    code: MicroChallengeCode
    category: str
    title: str
    icon: str
    minutes: int
    hint: str


class SlumpStatusResponse(BaseModel):
    is_slump: bool
    days_since_last_checkin: int
    threshold_days: int
    micro: MicroChallengeDTO
    already_checked_in_today: bool


class SlumpMicroCheckinRequest(BaseModel):
    micro_code: Annotated[MicroChallengeCode, Field(description="체크인할 마이크로 챌린지 코드")]


class SlumpMicroCheckinResponse(BaseModel):
    recovered: bool
    micro_code: MicroChallengeCode
    checked_at: datetime
    message: str
