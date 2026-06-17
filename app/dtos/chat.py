from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.dtos.base import BaseSerializerModel


class ChatMessageCreateRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=2000, description="사용자 질문")]

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, v: str) -> str:
        """공백만 있는 질문 거부 (m-3)."""
        if not v.strip():
            raise ValueError("질문은 공백만으로 구성될 수 없습니다.")
        return v


class ChatMessageResponse(BaseSerializerModel):
    message_id: int  # 어시스턴트 답변 메시지 id — 프론트가 피드백을 연결할 때 사용
    answer: str
    created_at: datetime


class MessageFeedbackRequest(BaseModel):
    rating: Literal[1, -1] = Field(description="+1 도움됨 / -1 도움 안 됨")
    comment: Annotated[str | None, Field(default=None, max_length=500, description="선택적 사유")] = None

    @field_validator("comment")
    @classmethod
    def blank_comment_to_none(cls, v: str | None) -> str | None:
        """공백만 있는 코멘트는 None 으로 정규화."""
        if v is not None and not v.strip():
            return None
        return v


class MessageFeedbackResponse(BaseSerializerModel):
    message_id: int
    rating: int
    created_at: datetime
