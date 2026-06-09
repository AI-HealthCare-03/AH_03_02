"""ai_worker 엔트리포인트 — Redis Stream consumer 루프.

rag_jobs 스트림을 consumer group 으로 읽어 rag_task 에 위임하고, 결과를
rag_resp:{job_id} 스트림에 기록한다. 실행: python -m ai_worker.main
"""

from __future__ import annotations

import asyncio
import json

from redis.exceptions import ResponseError

from ai_worker.core import config
from ai_worker.core.logger import setup_logger
from ai_worker.core.redis_client import get_redis, get_sync_redis
from ai_worker.rag import graph as rag
from ai_worker.schemas.chat import ChatJob
from ai_worker.schemas.ckd import CkdJob
from ai_worker.tasks.ckd_task import handle_ckd_job
from ai_worker.tasks.rag_task import handle_chat_job
from ai_worker.tasks.token_streamer import TokenStreamer

logger = setup_logger("ai_worker")
_CONSUMER = "worker-1"


def _warmup() -> None:
    """RAG 클라이언트 콜드스타트 제거 — startup에서 embedding/LLM을 1회 더미 호출.

    embedder·llm_client는 lazy 싱글턴이라 첫 사용자 요청에서 httpx 연결·클라이언트
    생성 지연(측정상 embedding ~4s + LLM ~1.8s)이 발생한다. 이 초기화를 startup으로
    옮겨 첫 요청 체감을 ~12s → ~5s로 줄인다. 실패해도 무시 — 첫 요청에서 자연 초기화된다.
    """
    try:
        from ai_worker.rag import embedder, llm_client

        embedder.embed_query("warmup")
        llm_client.get_gen_llm().invoke("ping")
        llm_client.get_grade_llm().invoke("ping")
        logger.info("RAG warmup 완료 — embedding·LLM 클라이언트 초기화됨")
    except Exception:  # noqa: BLE001 — 워밍업 실패가 worker 기동을 막지 않도록
        logger.warning("RAG warmup 실패 — 첫 요청에서 초기화됨", exc_info=True)


async def ensure_group(redis) -> None:
    """consumer group 생성 (이미 있으면 무시). 스트림이 없어도 mkstream 으로 생성."""
    try:
        await redis.xgroup_create(config.RAG_JOBS_STREAM, config.RAG_JOBS_GROUP, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def ensure_ckd_group(redis) -> None:
    try:
        await redis.xgroup_create(config.CKD_JOBS_STREAM, config.CKD_JOBS_GROUP, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def consume_ckd_once(redis) -> int:
    """ckd_jobs 한 번 읽어 예측·갱신. 실패는 로그 후 ack(무한 재처리 방지)."""
    resp = await redis.xreadgroup(
        config.CKD_JOBS_GROUP,
        _CONSUMER,
        {config.CKD_JOBS_STREAM: ">"},
        count=10,
        block=2000,
    )
    if not resp:
        return 0
    handled = 0
    for _stream, messages in resp:
        for msg_id, fields in messages:
            try:
                job = CkdJob(
                    health_check_id=int(fields["health_check_id"]),
                    egfr=float(fields["egfr"]) if fields.get("egfr") else None,
                    checked_date=fields["checked_date"],
                    payload=json.loads(fields["payload"]),
                )
                await handle_ckd_job(job)
            except Exception:  # noqa: BLE001 — 한 건 실패가 루프를 막지 않도록
                logger.exception("ckd job 처리 실패 — ack 후 계속")
            await redis.xack(config.CKD_JOBS_STREAM, config.CKD_JOBS_GROUP, msg_id)
            handled += 1
    return handled


async def consume_once(redis) -> int:
    """대기 중인 작업을 한 번 읽어 처리. 처리한 메시지 수 반환."""
    resp = await redis.xreadgroup(
        config.RAG_JOBS_GROUP,
        _CONSUMER,
        {config.RAG_JOBS_STREAM: ">"},
        count=10,
        block=2000,
    )
    if not resp:
        return 0
    handled = 0
    for _stream, messages in resp:
        for msg_id, fields in messages:
            job = ChatJob(
                job_id=fields["job_id"],
                question=fields["question"],
                user_context=json.loads(fields.get("user_context", "{}")),
                stream=(fields.get("stream") in ("1", "true", "True")),
            )
            resp_key = f"{config.RAG_RESP_PREFIX}:{job.job_id}"
            if job.stream:
                sink = TokenStreamer(get_sync_redis(), resp_key)
                try:
                    answer = await asyncio.to_thread(rag.run_stream, job.question, job.user_context, sink)
                    await redis.xadd(
                        resp_key, {"data": json.dumps({"type": "done", "answer": answer}, ensure_ascii=False)}
                    )
                except Exception as e:  # noqa: BLE001 — 실패도 클라이언트에 전달
                    await redis.xadd(
                        resp_key, {"data": json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)}
                    )
            else:
                result = await handle_chat_job(job)
                await redis.xadd(resp_key, {"data": result.model_dump_json()})
            await redis.xack(config.RAG_JOBS_STREAM, config.RAG_JOBS_GROUP, msg_id)
            handled += 1
    return handled


async def main() -> None:
    redis = get_redis()
    await ensure_group(redis)
    await ensure_ckd_group(redis)
    await asyncio.to_thread(_warmup)  # 콜드스타트 제거 (이벤트루프 안 막고 워밍)
    logger.info(
        "RAG consumer 시작 (stream=%s group=%s)",
        config.RAG_JOBS_STREAM,
        config.RAG_JOBS_GROUP,
    )
    while True:
        try:
            await asyncio.gather(consume_once(redis), consume_ckd_once(redis))
        except Exception:  # noqa: BLE001 — 루프는 죽지 않아야 함
            logger.exception("consume 루프 오류 — 계속 진행")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
