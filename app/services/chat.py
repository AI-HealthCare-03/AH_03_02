"""RAG 챗봇 서비스 — user_context 빌드 → Redis 작업 투입 → 응답 대기 → 영속화."""

from __future__ import annotations

import json
import uuid

from fastapi import HTTPException
from starlette import status

from app.core import config
from app.core.redis_client import get_redis
from app.dtos.chat import ChatMessageResponse
from app.models.chat import ChatRole
from app.models.health_check import HealthCheck
from app.repositories.chat_repository import ChatRepository


class ChatService:
    def __init__(self) -> None:
        self._repo = ChatRepository()

    async def _build_user_context(self, user_id: int) -> dict:
        """최신 검진에서 RAG 가 쓰는 eGFR·risk_group 추출. 없으면 {} (RAG 안전 분기)."""
        hc = await HealthCheck.filter(user_id=user_id).order_by("-checked_date").first()
        if hc is None:
            return {}
        ctx: dict = {}
        if hc.egfr_estimated is not None:
            ctx["eGFR"] = hc.egfr_estimated
        if hc.ckd_stage is not None:
            ctx["risk_group"] = str(hc.ckd_stage)
        if hc.weight is not None:
            ctx["weight"] = hc.weight  # 단백질 등 영양 권장량을 사용자 체중으로 개인화 환산
        return ctx

    async def ask(self, user_id: int, question: str) -> ChatMessageResponse:
        """질문을 RAG worker에 전달하고 답변을 받아 DB에 저장 후 반환한다.

        흐름:
        1. 사용자 검진 데이터에서 user_context(eGFR, risk_group) 추출
        2. Redis rag_jobs 스트림에 작업 투입
        3. rag_resp:{job_id} 스트림에서 응답 대기 (block)
        4. 성공 시에만 USER·ASSISTANT 메시지를 함께 DB 저장 후 반환

        Raises:
            HTTPException 504: RAG_TIMEOUT_SEC 초과 시
            HTTPException 500: worker가 error 페이로드 반환 시, 또는 answer가 비어있을 시
        """
        redis = get_redis()
        user_context = await self._build_user_context(user_id)
        job_id = uuid.uuid4().hex

        # I-1 고아 방지: USER 메시지 저장을 성공 확인 후로 이동
        await redis.xadd(
            config.RAG_JOBS_STREAM,
            {
                "job_id": job_id,
                "question": question,
                "user_context": json.dumps(user_context),
            },
        )

        resp_key = f"{config.RAG_RESP_PREFIX}:{job_id}"
        result = await redis.xread({resp_key: "0"}, count=1, block=config.RAG_TIMEOUT_SEC * 1000)
        if not result:
            # I-2: 타임아웃 시에도 잔여 키 정리 (worker가 늦게 쓴 경우 대비)
            await redis.delete(resp_key)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="답변 생성이 지연되고 있습니다. 잠시 후 다시 시도해주세요.",
            )
        # I-2: 응답을 정상적으로 읽은 직후 스트림 삭제 (Redis 메모리 누수 방지)
        await redis.delete(resp_key)
        payload = json.loads(result[0][1][0][1]["data"])
        if payload.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="답변 생성 중 오류가 발생했습니다.",
            )
        # C-1 null/빈 문자열 가드: answer가 없으면 즉시 500
        answer = payload.get("answer")
        if not answer:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="답변 생성 결과가 비어있습니다.",
            )
        # 성공 경로에서만 USER·ASSISTANT 메시지를 함께 저장 (I-1)
        await self._repo.add(user_id=user_id, role=ChatRole.USER, content=question)
        saved = await self._repo.add(user_id=user_id, role=ChatRole.ASSISTANT, content=answer)
        return ChatMessageResponse(answer=answer, created_at=saved.created_at)
