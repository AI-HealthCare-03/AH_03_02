"""ai_worker용 Redis 비동기·동기 클라이언트."""

from __future__ import annotations

import redis
import redis.asyncio as aioredis

from ai_worker.core import config

_client: aioredis.Redis | None = None
_sync_client: redis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
            decode_responses=True,
        )
    return _client


def get_sync_redis() -> redis.Redis:
    """동기 Redis 클라이언트 lazy 싱글턴.

    asyncio.to_thread 내부(generate 노드)에서 xadd를 동기적으로 호출하기 위해 사용.
    decode_responses=True — 비동기 클라이언트와 동일하게 str 반환.
    """
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            decode_responses=True,
        )
    return _sync_client
