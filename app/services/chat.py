"""RAG 챗봇 서비스 — user_context 빌드 → Redis 작업 투입 → 응답 대기 → 영속화."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from starlette import status

from app.core import config
from app.core.redis_client import get_redis
from app.dtos.chat import ChatMessageResponse, MessageFeedbackResponse
from app.models.chat import ChatRole
from app.models.health_check import HealthCheck
from app.models.lifestyle_survey import LifestyleSurvey
from app.repositories.chat_repository import ChatRepository, MessageFeedbackRepository
from app.services.diet_flags import dialysis_to_track, load_diet_flags


def _sse(event: dict) -> str:
    """dict → SSE 'data: {json}\\n\\n' 프레임."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class ChatService:
    def __init__(self) -> None:
        self._repo = ChatRepository()
        self._fb_repo = MessageFeedbackRepository()

    async def _build_user_context(self, user_id: int) -> dict:  # noqa: C901
        """최신 검진·생활습관설문에서 eGFR·risk_group·track·ckd_cause + 식이 플래그 추출. 없으면 부분/빈 dict."""
        hc = await HealthCheck.filter(user_id=user_id).order_by("-checked_date", "-id").first()
        ctx: dict = {}
        if hc is not None:
            if hc.egfr_estimated is not None:
                ctx["eGFR"] = hc.egfr_estimated
            if hc.ckd_stage is not None:
                ctx["risk_group"] = str(hc.ckd_stage)
            if hc.weight is not None:
                ctx["weight"] = hc.weight  # 단백질 등 영양 권장량을 사용자 체중으로 개인화 환산
            if hc.dialysis_type is not None:
                track = dialysis_to_track(str(hc.dialysis_type))
                if track:
                    ctx["track"] = track
        # 원인질환 — load_diet_flags 가 LS 를 조회하나 DietFlagResult 만 반환해 재사용 불가 → 별도 조회
        # 같은 날 재제출 시 최신 문진을 보장하려면 id tiebreaker 필요(다른 최신-조회와 정합)
        ls = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()
        if ls is not None:
            causes = [
                c
                for c, flag in [
                    ("htn", ls.htn_diagnosed),
                    ("dm", ls.dm_diagnosed),
                    ("dyslipidemia", ls.dyslipidemia_diagnosed),
                ]
                if flag
            ]
            if causes:
                ctx["ckd_cause"] = causes
            if ls.ckd_diagnosed:
                ctx["ckd_diagnosed"] = True
        # 식이 플래그(챗봇 배경 컨텍스트 — P1 단방향, Q&A 모드라 자동 우회 안 함)
        flags = await load_diet_flags(user_id)
        if flags is not None and (flags.flags or flags.search_hints):
            ctx["diet_flags"] = {"flags": list(flags.flags), "search_hints": list(flags.search_hints)}
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
        return ChatMessageResponse(message_id=saved.id, answer=answer, created_at=saved.created_at)

    async def ask_stream(self, user_id: int, question: str) -> AsyncGenerator[str, None]:
        """RAG worker에 스트리밍 잡 발행 → rag_resp 청크를 SSE(data: ...) 로 점진 yield.

        token 누적 / reset 비움 / done 시 USER·ASSISTANT 메시지 저장 후 종료 / error·타임아웃 처리.
        기존 ask()와 달리 SSE 스트림을 반환한다. _build_user_context는 읽기 전용 재사용.
        """
        redis = get_redis()
        user_context = await self._build_user_context(user_id)
        job_id = uuid.uuid4().hex
        await redis.xadd(
            config.RAG_JOBS_STREAM,
            {
                "job_id": job_id,
                "question": question,
                "user_context": json.dumps(user_context),
                "stream": "1",
            },
        )
        resp_key = f"{config.RAG_RESP_PREFIX}:{job_id}"
        last_id = "0"
        full = ""
        try:
            while True:
                res = await redis.xread({resp_key: last_id}, count=50, block=config.RAG_TIMEOUT_SEC * 1000)
                if not res:
                    yield _sse({"type": "error", "error": "답변 생성이 지연되고 있습니다."})
                    return
                for _stream, entries in res:
                    for entry_id, fields in entries:
                        last_id = entry_id
                        ev = json.loads(fields["data"])
                        etype = ev.get("type")
                        if etype == "token":
                            full += ev.get("text", "")
                            yield _sse(ev)
                        elif etype == "reset":
                            full = ""
                            yield _sse(ev)
                        elif etype == "done":
                            full = ev.get("answer") or full
                            # 성공 시에만 USER·ASSISTANT 저장 (기존 ask 고아방지 정책과 동일)
                            await self._repo.add(user_id=user_id, role=ChatRole.USER, content=question)
                            saved = await self._repo.add(user_id=user_id, role=ChatRole.ASSISTANT, content=full)
                            # 프론트 피드백 연결용으로 저장된 어시스턴트 메시지 id 를 done 이벤트에 실어 보낸다
                            ev["message_id"] = saved.id
                            yield _sse(ev)
                            return
                        elif etype == "error":
                            yield _sse(ev)
                            return
        finally:
            await redis.delete(resp_key)

    async def submit_feedback(
        self, *, user_id: int, message_id: int, rating: int, comment: str | None
    ) -> MessageFeedbackResponse:
        """AI 답변(어시스턴트 메시지)에 대한 사용자 피드백을 저장한다 (수집 → 저장 루프).

        본인 대화의 어시스턴트 메시지에만 허용. 같은 메시지에 재제출 시 upsert 로 갱신.

        Raises:
            HTTPException 404: 메시지가 존재하지 않을 때
            HTTPException 403: 본인 메시지가 아닐 때
            HTTPException 400: 사용자 질문(USER) 메시지에 피드백하려 할 때
        """
        msg = await self._repo.get_message(message_id)
        if msg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="메시지를 찾을 수 없습니다.")
        if msg.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="본인 대화의 답변에만 피드백할 수 있습니다."
            )
        if msg.role != ChatRole.ASSISTANT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI 답변에만 피드백할 수 있습니다.")
        fb = await self._fb_repo.upsert(user_id=user_id, chat_message_id=message_id, rating=rating, comment=comment)
        return MessageFeedbackResponse(message_id=message_id, rating=fb.rating, created_at=fb.created_at)
