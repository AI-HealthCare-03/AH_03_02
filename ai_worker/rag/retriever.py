"""Qdrant 검색 (ai_worker/rag/retriever.py).

child top-k 벡터검색(age_group=adult 필터) → 각 child 의 parent_id 로 parent 맥락 조회.
2026-05-30 골든질문 스모크에서 검증한 경로를 모듈화한다.

인덱싱 uploader 가 커스텀 payload(`text`·`parent_id`·`age_group`)로 직접 적재했고 Parent-Child
구조를 정확히 다뤄야 하므로, langchain `QdrantVectorStore` 대신 qdrant-client 를 직접 쓴다.
point id 는 인덱싱 `qdrant_uploader.point_id` 와 동일하게 16-hex → int(hex,16) 로 변환한다.
"""

from __future__ import annotations

import logging
import re as _re
import time

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
from rank_bm25 import BM25Okapi

from . import config as cfg
from . import embedder

logger = logging.getLogger("ai_worker.rag")

_client: QdrantClient | None = None

# ── 동의어 그룹 ─────────────────────────────────────────────────────────────────
# 쌍이 아닌 그룹으로 관리 — 추후 3개 이상 추가 시 frozenset만 확장.
SYNONYM_GROUPS: list[frozenset[str]] = [
    frozenset({"신장", "콩팥"}),
    frozenset({"만성신부전", "만성콩팥병"}),
    frozenset({"신부전", "콩팥기능저하"}),
    frozenset({"신장병", "콩팥병"}),
    frozenset({"포타슘", "칼륨"}),
    frozenset({"소듐", "나트륨"}),
    frozenset({"phosphorus", "인"}),
    frozenset({"이상지질혈증", "고지혈증"}),
]

# 긴 항 우선 매칭 (만성신부전>신부전, 신장병>신장) — 모듈 로드 시 1회 계산.
_SYN_SORTED: list[tuple[int, str, frozenset[str]]] = sorted(
    [(len(t), t, g) for g in SYNONYM_GROUPS for t in g],
    key=lambda x: x[0],
    reverse=True,
)

# 기관·직역 고유 표현만 보호 — "콩팥내과/콩팥학회"는 비표준 의료 용어.
# 신장이식·신장암·신장결석 등 임상 복합어는 "콩팥OO"도 통용되므로 보호 불필요.
_PROTECTED_COMPOUNDS: frozenset[str] = frozenset({"신장내과", "신장전문의", "신장학회", "신장학"})

# ── CKD 진단자 후처리 필터 상수 ───────────────────────────────────────────────
# GENERAL_SOURCES: 일반인 대상 출처 — CKD 식이·수치 기준과 상충 가능
GENERAL_SOURCES: frozenset[str] = frozenset(
    {
        "16.대한고혈압학회 - 2026 제6판 고혈압 진료지침",
        "당뇨병과 고혈압·이상지질혈증 _ 지식백과",
        "저혈당 대처법 _ 지식백과",
        "당뇨인의 식사요법 원칙 _ 지식백과",
    }
)
# MIXED_SOURCE: general+CKD 혼재 — h2로 CKD 챕터 구분 (B2 확인: 완전일치)
MIXED_SOURCE = "2025 당뇨병 진료지침_전문_최종본"
# M1 확인: 6개 키워드로 MIXED_SOURCE CKD h2 34청크 전량 포착 (누락 없음)
_CKD_H2_KEYWORDS: frozenset[str] = frozenset(
    {
        "신장질환",
        "콩팥",
        "신장내과",
        "만성신장",
        "신대체",
        "CKD",
    }
)
# 주의: "인" 단독 금지(오탐) — "인산"/"인 제한"/"고인산"으로만 매칭
CONFLICT_KEYWORDS: tuple[str, ...] = (
    "나트륨",
    "소금",
    "저염",
    "칼륨",
    "포타슘",
    "인산",
    "인 제한",
    "고인산",
    "단백질",
    "수분 제한",
    "물 제한",
    "혈압 목표",
    "목표 혈압",
)


def _is_ckd_h2(h2: str) -> bool:
    """MIXED_SOURCE 청크가 CKD 챕터인지 h2로 판정 — CKD 챕터는 필터 제외."""
    return any(kw in h2 for kw in _CKD_H2_KEYWORDS)


def _is_general_conflicting(h) -> bool:  # noqa: ANN001
    """CKD 진단자에게 상충될 수 있는 general 출처 청크인지 판정."""
    p = h.payload or {}
    src = p.get("source", "")
    h2 = p.get("h2") or ""
    is_general = src in GENERAL_SOURCES or (src == MIXED_SOURCE and not _is_ckd_h2(h2))
    if not is_general:
        return False
    combined = h2 + " " + (p.get("text") or "")
    return any(kw in combined for kw in CONFLICT_KEYWORDS)


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=cfg.QDRANT_URL)
    return _client


def _parent_point_id(parent_hex: str) -> int:
    """인덱싱 uploader.point_id 와 동일 규칙 (16-hex → u64)."""
    return int(parent_hex, 16)


def _bm25_scores(query: str, texts: list[str]) -> list[float]:
    """BM25Okapi 점수 반환 (한국어: 공백 토크나이저)."""
    tokenized = [t.split() for t in texts]
    bm25 = BM25Okapi(tokenized)
    return bm25.get_scores(query.split()).tolist()


def _rrf_rerank(hits: list, bm25_scores: list[float], *, k: int, top_k: int) -> list:
    """코사인 순위 + BM25 순위를 RRF로 통합, top_k개 반환."""
    n = len(hits)
    bm25_rank = {i: r for r, i in enumerate(sorted(range(n), key=lambda x: bm25_scores[x], reverse=True))}
    rrf_scores = [1 / (k + ci) + 1 / (k + bm25_rank[ci]) for ci in range(n)]
    order = sorted(range(n), key=lambda i: rrf_scores[i], reverse=True)
    return [hits[i] for i in order[:top_k]]


def _find_term(query: str, term: str) -> int:
    """쿼리에서 term 시작 인덱스 반환(-1=없음).

    1자 단어(예: "인")만 단어 경계 검사 — "인슐린"의 "인" 오매칭 방지.
    2자 이상은 substring 매칭 — 한국어 조사 붙임 대응("콩팥의"에서 "콩팥" 매칭).
    """
    if len(term) != 1:
        return query.find(term)  # 2자 이상: 경계 검사 없음
    # 1자: 앞뒤 경계 검사
    pos = 0
    while True:
        idx = query.find(term, pos)
        if idx == -1:
            return -1
        end = idx + 1
        before_ok = idx == 0 or not query[idx - 1].isalnum()
        after_ok = end >= len(query) or not query[end].isalnum()
        if before_ok and after_ok:
            return idx
        pos = idx + 1


_HEIGHT_RE = _re.compile(r"신장\s*\d")  # "신장 165cm" 등 키(身長) 표현


def _is_protected(query: str, idx: int, end: int) -> bool:
    """매칭 위치(idx, end)가 보호 복합어 또는 키(身長) 표현 안에 있으면 True."""
    for compound in _PROTECTED_COMPOUNDS:
        p = query.find(compound)
        if p != -1 and p <= idx and end <= p + len(compound):
            return True
    # "신장 165" 등 신장(키) 표현 — 숫자 앞의 신장은 확장 불가
    for m in _HEIGHT_RE.finditer(query):
        if m.start() <= idx < m.end():
            return True
    return False


def _expand_queries(query: str) -> list[str]:
    """쿼리 내 동의어를 탐지해 원본 + 확장 변형 리스트 반환.

    "신장 기능이란" → ["신장 기능이란", "콩팥 기능이란"]
    동의어 없으면 [query].

    설계 원칙:
    - 치환 아닌 확장: 원본 쿼리 검색은 유지, 동의어 쿼리 추가.
    - 긴 항 우선 매칭: "만성신부전"을 먼저 잡아 "신부전" 중복 확장 방지.
    - 기관·직역·키 보호: _PROTECTED_COMPOUNDS + 신장(키) 표현은 확장 안 함.
    - 매칭된 범위 추적: 한 위치는 한 그룹만 적용.
    """
    variants: list[str] = [query]
    matched: list[tuple[int, int]] = []  # (start, end) 이미 매칭된 범위

    for _, term, group in _SYN_SORTED:
        idx = _find_term(query, term)
        if idx == -1:
            continue
        end = idx + len(term)
        if any(s < end and idx < e for s, e in matched):
            continue  # 이미 매칭된 범위와 겹침 → 건너뜀
        matched.append((idx, end))
        if _is_protected(query, idx, end):
            continue  # 기관·직역·키 표현 → 확장 생략
        for alt in group:
            if alt != term:
                expanded = query[:idx] + alt + query[end:]
                if expanded not in variants:
                    variants.append(expanded)

    return variants


def _build_filter(age_group: str, track: str | None) -> Filter:
    """track 설정에 따른 Qdrant 필터 생성."""
    must: list = [FieldCondition(key="age_group", match=MatchValue(value=age_group))]
    if track:
        if track in cfg.DIALYSIS_SUBTRACKS:
            allowed = [track, cfg.TRACK_DIALYSIS, cfg.TRACK_COMMON]
        else:
            allowed = [track, cfg.TRACK_COMMON]
    else:
        allowed = [cfg.TRACK_COMMON]
    must.append(FieldCondition(key="track", match=MatchAny(any=allowed)))
    return Filter(must=must)


def _multi_search(
    queries: list[str],
    flt: Filter,
    client: QdrantClient,
    query_vector: list[float] | None,
    top_k: int,
    orig_query: str,
) -> tuple[list, float]:
    """확장 쿼리 리스트로 멀티 검색 → dedup → rerank → (hits, raw_max_score)."""
    seen: dict[int, object] = {}
    for i, q in enumerate(queries):
        _t = time.perf_counter()
        qv = query_vector if (i == 0 and query_vector is not None) else embedder.embed_query(q)
        if i == 0:
            logger.info("[RAG-TIMING]   retrieve.embed         elapsed=%.3fs", time.perf_counter() - _t)

        _t = time.perf_counter()
        hits = client.query_points(
            collection_name=cfg.COLLECTION_CHILD,
            query=qv,
            limit=cfg.BM25_OVER_FETCH,
            query_filter=flt,
        ).points
        if i == 0:
            logger.info("[RAG-TIMING]   retrieve.qdrant_child  elapsed=%.3fs", time.perf_counter() - _t)

        for h in hits:
            if h.id not in seen or h.score > seen[h.id].score:
                seen[h.id] = h

    merged = sorted(seen.values(), key=lambda h: h.score, reverse=True)
    if len(merged) > cfg.BM25_OVER_FETCH:
        merged = merged[: cfg.BM25_OVER_FETCH]

    raw_max = merged[0].score if merged else 0.0

    if merged:
        texts = [(h.payload or {}).get("text", "") for h in merged]
        if len(queries) == 1:
            # 단일 쿼리: BM25+RRF
            merged = _rrf_rerank(merged, _bm25_scores(orig_query, texts), k=cfg.RRF_K, top_k=top_k)
        else:
            # 확장 쿼리: BM25 생략, 임베딩 점수 순 유지
            # 한국어 조사("콩팥은"≠"콩팥")로 BM25가 확장 결과를 역강등하는 문제 방지
            merged = merged[:top_k]
        logger.info("[RAG-RRF]  candidates=%d → final=%d (queries=%d)", len(texts), len(merged), len(queries))

    return merged, raw_max


def retrieve(
    query: str,
    *,
    top_k: int = cfg.TOP_K,
    age_group: str = cfg.AGE_GROUP,
    track: str | None = None,
    client: QdrantClient | None = None,
    query_vector: list[float] | None = None,
    ckd_diagnosed: bool = False,
) -> tuple[list[Document], str, float]:
    """질문 → child 검색(age_group 필터, 선택적 track OR 필터) → parent 맥락 조회.

    track 지정 시: age_group=adult AND track IN [track, "common"]
      → 해당 트랙 전용 청크 + 공통 청크만 반환, 다른 트랙 청크 제외.
    track=None(기본): age_group=adult 만 — 하위 호환.
    반환: (documents=child Document 리스트, parent_context=parent 텍스트 결합, top_score).
    client·query_vector 주입 가능 (테스트는 mock client + 벡터 주입으로 키·네트워크 불요).
    query_vector 주입 시 동의어 확장 생략 (테스트 결정론성 유지).
    """
    client = client or get_client()
    flt = _build_filter(age_group, track)
    queries = [query] if query_vector is not None else _expand_queries(query)
    hits, raw_max_score = _multi_search(queries, flt, client, query_vector, top_k, query)

    if ckd_diagnosed and hits:
        before = len(hits)
        hits = [h for h in hits if not _is_general_conflicting(h)]
        if len(hits) < before:
            logger.info("[RAG-FILTER] ckd_diagnosed removed=%d remaining=%d", before - len(hits), len(hits))

    documents: list[Document] = []
    parent_ids: list[str] = []
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

    top_score = max((h.score for h in hits), default=0.0) if ckd_diagnosed else raw_max_score
    return documents, parent_context, top_score
