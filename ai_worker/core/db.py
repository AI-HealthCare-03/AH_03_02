"""ai_worker용 Postgres 직접 접근 (asyncpg).

app.models(Tortoise)를 import하지 않고 health_checks를 raw SQL로 갱신한다.
컨테이너 분리(ai_worker→app cross-import 금지)를 유지하기 위함이다.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from ai_worker.core import config

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            min_size=1,
            max_size=5,
        )
    return _pool


async def update_prediction(
    health_check_id: int,
    ckd_risk_score: float,
    app_group: str,
    shap_model1: Any = None,
    shap_model2: Any = None,
) -> None:
    """예측 결과로 health_checks 갱신. eGFR·ckd_stage는 app 동기값을 유지(미갱신).

    shap_model1·shap_model2: None이면 DB에 NULL 저장. 값이 있으면 JSONB로 직렬화.
    app_group: 현재 값이 CKD/DIALYSIS(진단자 그룹)면 모델 점수로 덮어쓰지 않는다
    (risk_score·shap는 진단자에게도 갱신, app_group만 보호).
    """
    pool = await get_pool()
    shap1_json = json.dumps(shap_model1, ensure_ascii=False) if shap_model1 is not None else None
    shap2_json = json.dumps(shap_model2, ensure_ascii=False) if shap_model2 is not None else None
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE health_checks
               SET ckd_risk_score = $1,
                   app_group = CASE
                       WHEN app_group IN ('CKD', 'DIALYSIS') THEN app_group
                       ELSE $2
                   END,
                   shap_model1 = $3::jsonb,
                   shap_model2 = $4::jsonb
             WHERE id = $5""",
            ckd_risk_score,
            app_group,
            shap1_json,
            shap2_json,
            health_check_id,
        )


async def update_guide(health_check_id: int, ai_guide: str) -> None:
    """RAG 선생성 AI 가이드를 health_checks.ai_guide에 저장."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE health_checks SET ai_guide = $1 WHERE id = $2",
            ai_guide,
            health_check_id,
        )
