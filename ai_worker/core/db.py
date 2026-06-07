"""ai_worker용 Postgres 직접 접근 (asyncpg).

app.models(Tortoise)를 import하지 않고 health_checks를 raw SQL로 갱신한다.
컨테이너 분리(ai_worker→app cross-import 금지)를 유지하기 위함이다.
"""

from __future__ import annotations

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


async def update_prediction(health_check_id: int, ckd_risk_score: float, app_group: str) -> None:
    """예측 결과로 health_checks 갱신. eGFR·ckd_stage는 app 동기값을 유지(미갱신)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE health_checks SET ckd_risk_score = $1, app_group = $2 WHERE id = $3",
            ckd_risk_score,
            app_group,
            health_check_id,
        )
