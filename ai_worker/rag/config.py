"""RAG 추론 설정 (ai_worker/rag/config.py) — 추론 트랙 단일 진실.

⚠ collection·임베딩 모델은 인덱싱 트랙 `src/rag_indexing/config.py`와 **반드시 동일**해야 한다.
  두 패키지가 top-level로 분리돼 직접 import가 어려우므로 값을 복제하고 여기 주석으로 동기화를
  표시한다. 한쪽을 바꾸면 다른 쪽도 같이 바꿀 것.
"""

from __future__ import annotations

import os

# ─────────────────────────────────────────────
# Qdrant — 로컬 스크립트 기본 localhost. docker 내부 실행 시 env QDRANT_URL=http://qdrant:6333
# ─────────────────────────────────────────────
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
# 환경변수 우선 — 운영(prod)에선 .env의 medical_kb_prod / 로컬 dev에선 default medical_kb_dev 가능
COLLECTION_CHILD = os.getenv("QDRANT_COLLECTION_NAME", "medical_kb_dev")
COLLECTION_PARENT = "medical_kb_parents"  # = src/rag_indexing/config.COLLECTION_PARENT

# ─────────────────────────────────────────────
# OpenAI 모델 — collection 차원과 반드시 일치 (small=1536d, large=3072d)
# ─────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
GEN_TEMPERATURE = 0.0  # 생성: 결정적 — 같은 질문에 일관된 답변(의료 정보는 변동성 최소화)
GRADE_TEMPERATURE = 0.0  # 채점·재작성: 결정적

# ─────────────────────────────────────────────
# 검색
# ─────────────────────────────────────────────
TOP_K = 5
AGE_GROUP = "adult"  # 성인 서비스 — 소아(pediatric) 청크 격리 (P1-4 태깅 활용)
SCORE_PREPASS = 0.55  # top_score≥이 값이면 grade LLM 건너뛰고 relevant 자동통과 (over-refusal 방지)

BM25_OVER_FETCH = 15  # RRF용 후보 over-fetch 수 (TOP_K * 3)
RRF_K = 60  # RRF 표준 상수
# (PoC 발견: grade LLM이 정답 청크 score 0.6도 과필터)

# ─────────────────────────────────────────────
# Self-corrective / Self-RAG 재시도 상한 (PoC 검증값)
# ─────────────────────────────────────────────
MAX_REWRITE = 2  # 관련성 부족·미해결 → rewrite 후 재검색 (retry_count < 2 → 최대 2회)
# ⚠ 의미: hallucination_node가 매 실행 gen_retry_count += 1 하므로 "실제 재생성 = MAX_GEN_RETRY - 1".
#   현재 2 → 재생성 1회. (1차 환각: 0→1, 1<2 재생성 / 2차: 1→2, 2<2 거짓 → 종료)
#   '재생성 N회'로 바꾸려면 N+1 로 설정할 것.
MAX_GEN_RETRY = 2

# ─────────────────────────────────────────────
# LLM 폴백 (검색 실패 시 차등 라우팅 — medical 검증)
# ─────────────────────────────────────────────
FALLBACK_MAX_TOKENS = 500  # 폴백 답변 길이 제한 (긴 답변일수록 환각·위험정보 노출↑)

# ─────────────────────────────────────────────
# track 값 (= src/rag_indexing/config.TRACK_* — 양쪽 동기화 유지)
# ─────────────────────────────────────────────
TRACK_NON_DIALYSIS = "non_dialysis"
TRACK_HEMODIALYSIS = "hemodialysis"
TRACK_PERITONEAL = "peritoneal"
TRACK_DIALYSIS = "dialysis"  # 혈액·복막 구분 없는 투석 공통
TRACK_TRANSPLANT = "transplant"
TRACK_COMMON = "common"

# hemodialysis/peritoneal 검색 시 dialysis(투석 공통) 도 포함할 트랙 집합
DIALYSIS_SUBTRACKS: frozenset = frozenset({TRACK_HEMODIALYSIS, TRACK_PERITONEAL})
