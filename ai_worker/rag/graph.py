"""LangGraph StateGraph 조립 (ai_worker/rag/graph.py) — Self-corrective RAG.

guard → retrieve → grade ─(부족)→ rewrite → retrieve(≤2)
       → generate → hallucination ─(환각)→ generate(≤1) / answer_grade
                   → answer_grade ─(미해결)→ rewrite → post_guard → END

컴파일된 그래프는 모듈 lazy 싱글턴으로 1회만 만든다(노드 함수의 LLM은 호출 시점 lazy라 컴파일에
키 불요). Phase 5에서 ai_worker task가 get_graph().invoke(...) 로 호출한다.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import RAGState

_graph = None


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
        b.add_node(name, fn)

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


def run(question: str, user_context: dict | None = None) -> str:
    """단일 질문 실행 → 최종 답변 문자열 (차단 시 가드 응답)."""
    init = {
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
    }
    final = get_graph().invoke(init)
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
    print("[그래프 컴파일] 노드 8 + 조건부 엣지 4")
    for q, uc in cases:
        print(f"\n{'=' * 72}\n질문: {q}" + (f"  (user_context={uc})" if uc else ""))
        print(f"{'─' * 72}")
        print(run(q, uc))
