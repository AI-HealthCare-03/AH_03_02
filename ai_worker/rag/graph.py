"""LangGraph StateGraph 조립 (ai_worker/rag/graph.py) — Self-corrective RAG.

guard → retrieve → grade ─(부족)→ rewrite → retrieve(≤2)
       → generate → hallucination ─(환각)→ generate(≤1) / answer_grade
                   → answer_grade ─(미해결)→ rewrite
                   → analogy → post_guard → END

컴파일된 그래프는 모듈 lazy 싱글턴으로 1회만 만든다(노드 함수의 LLM은 호출 시점 lazy라 컴파일에
키 불요). Phase 5에서 ai_worker task가 get_graph().invoke(...) 로 호출한다.
"""

from __future__ import annotations

import logging
import time

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import RAGState

logger = logging.getLogger("ai_worker.rag")

_graph = None


def _timed(name: str, fn):
    """노드 실행 시간을 [RAG-TIMING] 로그로 남기는 래퍼 (병목 계측용).

    반환값을 그대로 통과시켜 그래프 동작은 불변. 같은 노드가 여러 번 호출되면
    (rewrite/generate 루프) 호출마다 1줄씩 찍혀 호출 횟수도 함께 드러난다.
    """

    def wrapper(state):
        t0 = time.perf_counter()
        result = fn(state)
        logger.info("[RAG-TIMING] node=%-18s elapsed=%.3fs", name, time.perf_counter() - t0)
        return result

    return wrapper


def build_graph():
    b = StateGraph(RAGState)
    for name, fn in [
        ("guard", nodes.guard_node),
        ("retrieve", nodes.retrieve_node),
        ("grade", nodes.grade_node),
        ("rewrite", nodes.rewrite_node),
        ("generate", nodes.generate_node),
        ("hallucination", nodes.hallucination_node),
        ("answer_grade", nodes.answer_node),
        ("analogy", nodes.analogy_node),
        ("post_guard", nodes.post_guard_node),
        # 검색 실패 폴백 차등 라우팅
        ("classify_fallback", nodes.classify_fallback_node),
        ("fallback_generate", nodes.fallback_generate_node),
        ("fallback_post_guard", nodes.fallback_post_guard_node),
        ("referral_notice", nodes.referral_notice_node),
        ("scope_notice", nodes.scope_notice_node),
    ]:
        b.add_node(name, _timed(name, fn))

    b.add_edge(START, "guard")
    # guard: 차단 메시지가 있으면 즉시 END (검색 건너뜀)
    b.add_conditional_edges(
        "guard",
        lambda s: "blocked" if s.get("blocked") else "retrieve",
        {"blocked": END, "retrieve": "retrieve"},
    )
    b.add_edge("retrieve", "grade")
    b.add_conditional_edges(
        "grade",
        nodes.relevance_router,
        {"generate": "generate", "rewrite": "rewrite", "classify_fallback": "classify_fallback"},
    )
    b.add_edge("rewrite", "retrieve")
    b.add_edge("generate", "hallucination")
    b.add_conditional_edges(
        "hallucination",
        nodes.grounded_router,
        {"generate": "generate", "answer_grade": "answer_grade", "post_guard": "analogy"},
    )
    b.add_conditional_edges("answer_grade", nodes.answer_router, {"post_guard": "analogy", "rewrite": "rewrite"})
    b.add_edge("analogy", "post_guard")
    b.add_edge("post_guard", END)

    # 검색 실패 폴백 분기
    b.add_conditional_edges(
        "classify_fallback",
        nodes.fallback_router,
        {
            "blocked": END,
            "fallback_generate": "fallback_generate",
            "referral": "referral_notice",
            "scope": "scope_notice",
        },
    )
    b.add_edge("fallback_generate", "fallback_post_guard")
    b.add_edge("fallback_post_guard", END)
    b.add_edge("referral_notice", END)
    b.add_edge("scope_notice", END)
    return b.compile()


def get_graph():
    """컴파일된 그래프 lazy 싱글턴."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def _init_state(question: str, user_context: dict | None, token_sink=None) -> dict:  # noqa: ANN001
    """그래프 초기 상태 딕셔너리 생성 헬퍼 (run·run_stream 공통)."""
    return {
        "messages": [{"role": "user", "content": question}],
        "documents": [],
        "parent_context": "",
        "top_score": 0.0,
        "relevance": "",
        "grounded": "",
        "addresses": "",
        "generation": "",
        "retry_count": 0,
        "gen_retry_count": 0,
        "blocked": None,
        "domain": "",
        "user_context": user_context or {},
        "token_sink": token_sink,
    }


def run(question: str, user_context: dict | None = None) -> str:
    """단일 질문 실행 → 최종 답변 문자열 (차단 시 가드 응답)."""
    t0 = time.perf_counter()
    final = get_graph().invoke(_init_state(question, user_context))
    logger.info("[RAG-TIMING] TOTAL graph.invoke elapsed=%.3fs", time.perf_counter() - t0)
    return final.get("blocked") or final.get("generation", "")


def run_stream(question: str, user_context: dict | None, sink) -> str:  # noqa: ANN001
    """스트리밍용 실행 — generate가 sink로 토큰 방출. 최종 답변 문자열 반환(차단 시 가드 응답)."""
    t0 = time.perf_counter()
    final = get_graph().invoke(_init_state(question, user_context, sink))
    logger.info("[RAG-TIMING] TOTAL graph.invoke(stream) elapsed=%.3fs", time.perf_counter() - t0)
    return final.get("blocked") or final.get("generation", "")


if __name__ == "__main__":
    # ⚠ 상대 import 때문에 반드시 패키지로 실행: cd 코드루트 && python -m ai_worker.rag.graph
    import sys

    # 통합 스모크 (실제 Qdrant + OPENAI_API_KEY 필요)
    cases = [
        ("만성콩팥병 환자의 하루 단백질 섭취 권장량은?", None),
        ("너무 힘들어서 죽고 싶어", None),
        ("운동 챌린지 추천해줘", {"eGFR": 25, "risk_group": "G4"}),
    ]
    if len(sys.argv) > 1:
        cases = [(" ".join(sys.argv[1:]), None)]
    print("[그래프 컴파일] 정상경로 노드 9(analogy 포함) + 조건부 엣지 5")
    for q, uc in cases:
        print(f"\n{'=' * 72}\n질문: {q}" + (f"  (user_context={uc})" if uc else ""))
        print(f"{'─' * 72}")
        print(run(q, uc))
