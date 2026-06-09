"""백엔드 ↔ ai_worker Redis Stream 페이로드 스키마."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatJob(BaseModel):
    job_id: str
    question: str
    user_context: dict = Field(default_factory=dict)
    stream: bool = False


class ChatResult(BaseModel):
    answer: str | None = None
    error: str | None = None
