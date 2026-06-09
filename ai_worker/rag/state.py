"""RAG 그래프 State (ai_worker/rag/state.py).

LangGraph `MessagesState`(messages + add_messages reducer)를 상속해 의료 RAG 필드를 더한다.
rewrite 노드가 messages 에 재작성 질문을 append 하므로 최근 human 메시지가 현재 질문이다.
"""

from __future__ import annotations

from langgraph.graph import MessagesState


class RAGState(MessagesState):
    # 검색
    documents: list  # 검색된 child (langchain Document)
    parent_context: str  # child 의 parent 맥락 (generate 입력 — Parent-Child)
    top_score: float  # 최상위 child 유사도 (grade 사전통과 판단)
    # Self-corrective / Self-RAG 채점 결과
    relevance: str  # relevant | not_relevant
    grounded: str  # grounded | not_grounded   (환각 검증)
    addresses: str  # addresses | not_addresses (질문 해결 검증)
    # 생성·재시도
    generation: str
    retry_count: int  # rewrite 횟수 (관련성·미해결)
    gen_retry_count: int  # 재생성 횟수 (환각)
    # 가드·폴백
    blocked: str | None  # pre-guard 차단 메시지 (있으면 즉시 END)
    domain: str  # 검색 실패 시 분류 (DOMAIN_1·DOMAIN_2_KIDNEY·DOMAIN_2_GENERAL·DOMAIN_3)
    user_context: dict  # {eGFR, risk_group, ...} — guard·prompt_builder 입력
    token_sink: object  # 스트리밍 토큰 싱크(있으면 generate가 토큰 방출). 비스트리밍은 미설정/None
