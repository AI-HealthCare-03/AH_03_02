"""StateGraph 노드 (ai_worker/rag/nodes.py) — PoC 9노드 이관 + 실제 모듈 연결.

흐름: guard → retrieve → grade ─(부족)→ rewrite → retrieve(재검색 ≤2)
            → generate → hallucination ─(환각)→ 재생성(≤1)
                        → answer_grade ─(미해결)→ rewrite
                        → analogy → post_guard → END
PoC(poc_langgraph_rag)의 노드·라우터 로직을 그대로 옮기되, 검색은 retriever(Parent-Child·age_group),
가드는 safety_guard(05 명세 전체), 프롬프트는 prompt_builder를 쓴다.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from . import config as cfg
from . import food_analogy, llm_client, prompt_builder, retriever, safety_guard
from .state import RAGState


def _q(state: RAGState) -> str:
    """가장 최근 사용자 질문 (rewrite로 갱신됐으면 그것)."""
    for m in reversed(state["messages"]):
        if getattr(m, "type", None) == "human":
            return m.content
        if isinstance(m, dict) and m.get("role") == "user":
            return m["content"]
    return ""


# ── 노드 ───────────────────────────────────────────────────────────────────────
def guard_node(state: RAGState) -> dict:
    blocked = safety_guard.pre_retrieval_guard(_q(state), state.get("user_context"))
    return {"blocked": blocked}


def retrieve_node(state: RAGState) -> dict:
    user_ctx = state.get("user_context") or {}
    track = user_ctx.get("track")  # None 이면 track 필터 미적용 (하위 호환)
    ckd_diagnosed = bool(user_ctx.get("ckd_diagnosed"))
    docs, parent_context, top = retriever.retrieve(_q(state), track=track, ckd_diagnosed=ckd_diagnosed)
    return {"documents": docs, "parent_context": parent_context, "top_score": top}


def grade_node(state: RAGState) -> dict:
    joined = "\n\n".join(d.page_content for d in state["documents"])
    if not joined.strip():
        return {"relevance": "not_relevant"}
    if state.get("top_score", 0.0) >= cfg.SCORE_PREPASS:
        return {"relevance": "relevant"}
    g = llm_client.doc_grader().invoke(f"질문: {_q(state)}\n문서:\n{joined}\n이 문서에 질문에 답할 정보가 있습니까?")
    return {"relevance": g.relevance}


def rewrite_node(state: RAGState) -> dict:
    nq = (
        llm_client.get_gen_llm()
        .invoke(f"다음 의료 질문을 벡터 검색에 더 잘 맞게 핵심 의학 용어 중심으로 한 줄로 재작성: {_q(state)}")
        .content
    )
    return {"messages": [HumanMessage(content=nq)], "retry_count": state.get("retry_count", 0) + 1}


def generate_node(state: RAGState) -> dict:
    msgs = prompt_builder.build_generation_messages(
        _q(state), state.get("parent_context", ""), state["documents"], state.get("user_context")
    )
    sink = state.get("token_sink")
    if sink is None:
        r = llm_client.get_gen_llm().invoke(msgs)
        return {"generation": r.content}
    sink.begin_generation()
    parts: list[str] = []
    for chunk in llm_client.get_gen_llm().stream(msgs):
        text = chunk.content or ""
        parts.append(text)
        sink.token(text)
    return {"generation": "".join(parts)}


def hallucination_node(state: RAGState) -> dict:
    ctx = state.get("parent_context") or "\n\n".join(d.page_content for d in state["documents"])
    g = llm_client.hallucination_grader().invoke(
        f"근거:\n{ctx}\n\n답변:\n{state['generation']}\n답변이 근거에 기반합니까?"
    )
    return {"grounded": g.grounded, "gen_retry_count": state.get("gen_retry_count", 0) + 1}


def answer_node(state: RAGState) -> dict:
    g = llm_client.answer_grader().invoke(f"질문: {_q(state)}\n답변: {state['generation']}\n답변이 질문을 해결합니까?")
    return {"addresses": g.addresses}


def analogy_node(state: RAGState) -> dict:
    """generate 답변의 영양 수치 마커를 음식 비유로 후처리(결정론적). hallucination 통과 후 실행."""
    gen = state.get("generation") or ""
    return {"generation": food_analogy.apply_analogies(gen)}


def post_guard_node(state: RAGState) -> dict:
    ans = state.get("generation") or "확실한 근거를 찾지 못했습니다. 신장내과 전문의와 상담하세요."
    forbidden = safety_guard.find_forbidden(ans)
    if "단백질처방수치" in forbidden:
        ans = safety_guard.add_protein_caveat_if_missing(ans, state.get("user_context", {}).get("app_group"))
        forbidden = [f for f in forbidden if f != "단백질처방수치"]
    if forbidden:
        ans += "\n\n※ 위 내용은 참고용 안내이며 단정적 의미가 아닙니다."
    return {"generation": safety_guard.with_disclaimer(ans)}


# ── 라우터 3종 (PoC 검증값) ────────────────────────────────────────────────────
def relevance_router(s: RAGState) -> str:
    if s["relevance"] == "relevant":
        return "generate"
    if s.get("retry_count", 0) < cfg.MAX_REWRITE:
        return "rewrite"
    return "classify_fallback"  # 검색 실패(rewrite 소진) → LLM 폴백 차등 라우팅


def grounded_router(s: RAGState) -> str:
    # gen_retry_count는 hallucination_node에서 +1 → 첫 환각 시 1. <2 라야 1회 재생성
    if s["grounded"] == "not_grounded":
        return "generate" if s.get("gen_retry_count", 0) < cfg.MAX_GEN_RETRY else "post_guard"
    return "answer_grade"


def answer_router(s: RAGState) -> str:
    if s["addresses"] == "addresses":
        return "post_guard"
    if s.get("retry_count", 0) < cfg.MAX_REWRITE:
        return "rewrite"
    return "post_guard"


# ── LLM 폴백 (검색 실패 차등 라우팅 — medical 검증 5필수 가드) ──────────────────
def classify_fallback_node(state: RAGState) -> dict:
    """검색 실패 질문을 4분류. medical 권장 #5: 분류 직전 응급·자해 재검사(멀티턴 대비)."""
    q = _q(state)
    blocked = safety_guard.pre_retrieval_guard(q, state.get("user_context"))
    if blocked:
        return {"blocked": blocked, "generation": blocked}
    ctx_hint = prompt_builder.build_classification_context_hint(state.get("user_context"))
    g = llm_client.domain_grader().invoke(
        f"{prompt_builder.CLASSIFICATION_SYSTEM_PROMPT}{ctx_hint}\n\n질문: {q}\n위 기준으로 분류하세요."
    )
    return {"domain": g.domain}


def fallback_generate_node(state: RAGState) -> dict:
    """가이드라인 근거 없이 LLM 일반지식 답변 (FALLBACK_SYSTEM_PROMPT 제약·max_tokens 제한)."""
    msgs = prompt_builder.build_fallback_messages(_q(state))
    llm = llm_client.get_gen_llm().bind(max_tokens=cfg.FALLBACK_MAX_TOKENS)
    sink = state.get("token_sink")
    if sink is None:
        r = llm.invoke(msgs)
        return {"generation": r.content}
    sink.begin_generation()
    parts: list[str] = []
    for chunk in llm.stream(msgs):
        text = chunk.content or ""
        parts.append(text)
        sink.token(text)
    return {"generation": "".join(parts)}


def fallback_post_guard_node(state: RAGState) -> dict:
    """폴백 답변 안전 확정 — 위험패턴(약물수치·독성·식이수치) 시 대체, 통과 시 폴백 면책."""
    return {"generation": safety_guard.fallback_finalize(state.get("generation", ""))}


def referral_notice_node(state: RAGState) -> dict:
    """DOMAIN_2_GENERAL(인접질환 비신장) → 전문진료 유도."""
    return {"generation": safety_guard.REFERRAL_NOTICE}


def scope_notice_node(state: RAGState) -> dict:
    """DOMAIN_3(비의료) → scope 안내."""
    return {"generation": safety_guard.SCOPE_NOTICE}


def fallback_router(s: RAGState) -> str:
    if s.get("blocked"):
        return "blocked"
    d = s.get("domain", "")
    if d in ("DOMAIN_1", "DOMAIN_2_KIDNEY"):
        return "fallback_generate"
    if d == "DOMAIN_2_GENERAL":
        return "referral"
    return "scope"  # DOMAIN_3 또는 분류 실패 시 안전하게 scope 안내
