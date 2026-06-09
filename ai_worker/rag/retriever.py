"""Qdrant 검색 (ai_worker/rag/retriever.py).

child top-k 벡터검색(age_group=adult 필터) → 각 child 의 parent_id 로 parent 맥락 조회.
2026-05-30 골든질문 스모크에서 검증한 경로를 모듈화한다.

인덱싱 uploader 가 커스텀 payload(`text`·`parent_id`·`age_group`)로 직접 적재했고 Parent-Child
구조를 정확히 다뤄야 하므로, langchain `QdrantVectorStore` 대신 qdrant-client 를 직접 쓴다.
point id 는 인덱싱 `qdrant_uploader.point_id` 와 동일하게 16-hex → int(hex,16) 로 변환한다.
"""

from __future__ import annotations

import logging
import time

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from . import config as cfg
from . import embedder

logger = logging.getLogger("ai_worker.rag")

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=cfg.QDRANT_URL)
    return _client


def _parent_point_id(parent_hex: str) -> int:
    """인덱싱 uploader.point_id 와 동일 규칙 (16-hex → u64)."""
    return int(parent_hex, 16)


def retrieve(
    query: str,
    *,
    top_k: int = cfg.TOP_K,
    age_group: str = cfg.AGE_GROUP,
    track: str | None = None,
    client: QdrantClient | None = None,
    query_vector: list[float] | None = None,
) -> tuple[list[Document], str, float]:
    """질문 → child 검색(age_group 필터, 선택적 track OR 필터) → parent 맥락 조회.

    track 지정 시: age_group=adult AND track IN [track, "common"]
      → 해당 트랙 전용 청크 + 공통 청크만 반환, 다른 트랙 청크 제외.
    track=None(기본): age_group=adult 만 — 하위 호환.
    반환: (documents=child Document 리스트, parent_context=parent 텍스트 결합, top_score).
    client·query_vector 주입 가능 (테스트는 mock client + 벡터 주입으로 키·네트워크 불요).
    """
    client = client or get_client()
    if query_vector is not None:
        qv = query_vector
    else:
        _t = time.perf_counter()
        qv = embedder.embed_query(query)
        logger.info("[RAG-TIMING]   retrieve.embed         elapsed=%.3fs", time.perf_counter() - _t)

    must_conditions: list = [FieldCondition(key="age_group", match=MatchValue(value=age_group))]
    if track:
        must_conditions.append(
            FieldCondition(key="track", match=MatchAny(any=[track, "common"]))
        )
    flt = Filter(must=must_conditions)
    _t = time.perf_counter()
    hits = client.query_points(
        collection_name=cfg.COLLECTION_CHILD,
        query=qv,
        limit=top_k,
        query_filter=flt,
    ).points
    logger.info("[RAG-TIMING]   retrieve.qdrant_child  elapsed=%.3fs", time.perf_counter() - _t)

    documents: list[Document] = []
    parent_ids: list[str] = []  # 순서 보존 + 중복 제거
    for h in hits:
        p = h.payload or {}
        documents.append(
            Document(
                page_content=p.get("text", ""),
                metadata={
                    "source": p.get("source"),
                    "page": p.get("page"),
                    "parent_id": p.get("parent_id"),
                    "doc_type": p.get("doc_type"),
                    "h2": p.get("h2"),
                    "score": h.score,
                },
            )
        )
        pid = p.get("parent_id")
        if pid and pid not in parent_ids:
            parent_ids.append(pid)

    parent_context = ""
    if parent_ids:
        _t = time.perf_counter()
        parents = client.retrieve(
            collection_name=cfg.COLLECTION_PARENT,
            ids=[_parent_point_id(pid) for pid in parent_ids],
        )
        logger.info("[RAG-TIMING]   retrieve.qdrant_parent elapsed=%.3fs", time.perf_counter() - _t)
        parent_context = "\n\n".join((pt.payload or {}).get("text", "") for pt in parents)

    top_score = hits[0].score if hits else 0.0
    return documents, parent_context, top_score
