"""SHAP Top 변수 → RAG 질문 빌드 + RAG worker 호출(chat 패턴 재사용).

chat.py의 ChatService.ask와 동일한 redis 발행→대기→정리 패턴을 사용하되,
메시지 DB 저장 없이 ai_guide 문자열만 반환한다.
실패·타임아웃 시 빈 문자열 반환 → 가이드 없이 리포트는 정상 제공.
"""

from __future__ import annotations

import json
import uuid

from app.core import config
from app.core.logger import setup_logger
from app.core.redis_client import get_redis

logger = setup_logger("report_guide")


def build_guide_question(
    shap_model1: list[dict],
    shap_model2: dict | None,
) -> str:
    """모델1 위험변수 Top3 + 모델2 생활습관 Top3을 자연어 질문으로 조합.

    RAG worker가 식이·운동·생활습관 관련 인덱싱 자료를 검색·생성하도록 구체적으로 구성.
    """
    # 모델1: 임상 위험 변수 Top3
    risk_features = ", ".join(item["feature"] for item in (shap_model1 or [])[:3])

    # 모델2: 생활습관 위험 요인 Top3 (items 키 아래 list)
    lifestyle_items = (shap_model2 or {}).get("items") or []
    life_features = ", ".join(item["feature"] for item in lifestyle_items[:3])

    return (
        f"다음은 한 사용자의 신장 건강 위험 기여 요인입니다. "
        f"검진 위험 변수: {risk_features or '특이사항 없음'}. "
        f"생활습관 위험 요인: {life_features or '특이사항 없음'}. "
        f"이 요인들을 개선하기 위한 식이·운동·생활습관 행동 가이드를 "
        f"구체적이고 실천 가능하게 항목별로 알려주세요."
    )


async def generate_guide(
    shap_model1: list[dict],
    shap_model2: dict | None,
    user_context: dict | None = None,
) -> str:
    """RAG worker에 질문 발행 → 응답 대기(chat 패턴).

    반환:
        RAG 응답 answer 문자열. 실패·타임아웃 시 빈 문자열.
    """
    redis = get_redis()
    question = build_guide_question(shap_model1, shap_model2)
    job_id = uuid.uuid4().hex

    try:
        await redis.xadd(
            config.RAG_JOBS_STREAM,
            {
                "job_id": job_id,
                "question": question,
                "user_context": json.dumps(user_context or {}),
            },
        )

        resp_key = f"{config.RAG_RESP_PREFIX}:{job_id}"
        result = await redis.xread({resp_key: "0"}, count=1, block=config.RAG_TIMEOUT_SEC * 1000)
        await redis.delete(resp_key)

        if not result:
            logger.warning("RAG 가이드 타임아웃 job_id=%s", job_id)
            return ""

        # chat.py와 동일한 인덱싱: result[0][1][0][1]["data"]
        payload = json.loads(result[0][1][0][1]["data"])
        if payload.get("error"):
            logger.warning("RAG 가이드 worker 오류 job_id=%s error=%s", job_id, payload.get("error"))
            return ""

        return payload.get("answer") or ""

    except Exception:  # noqa: BLE001 — 가이드 실패가 리포트 전체를 깨지 않도록
        logger.exception("RAG 가이드 생성 중 예외 job_id=%s", job_id)
        return ""
