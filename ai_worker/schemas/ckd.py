"""백엔드 → ai_worker CKD 예측 작업 페이로드 스키마."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CkdJob(BaseModel):
    health_check_id: int
    egfr: float | None = None  # app이 계산한 eGFR(1.012 보정) — run_inference egfr_override로 주입
    checked_date: str  # ISO date (나이 계산 기준일)
    payload: dict = Field(default_factory=dict)  # mapping.build_model_input이 받는 서비스 입력 dict
