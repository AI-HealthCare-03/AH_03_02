"""RAG 인덱싱 전역 상수 (단일 진실 공급원).

2026-05-29 RAG 심층점검(memory: project_rag_audit_2026-05-29) + probe_headers.py 실측 +
06_chunking_strategy 학습카드 + project_api_model_policy 기준.
chunking.py·embedder.py·qdrant_uploader.py 가 이 상수를 공유 import 한다.
"""

from __future__ import annotations

from pathlib import Path

# ─────────────────────────────────────────────
# 경로
# ─────────────────────────────────────────────
PKG_ROOT = Path(__file__).resolve().parent  # src/rag_indexing/
DATA_DIR = PKG_ROOT / "data"  # 원본 PDF/MD (PDF는 .gitignore)
CHUNKS_DIR = PKG_ROOT / "chunks"  # chunking.py JSONL 덤프 출력 (.gitignore 권장)

# ─────────────────────────────────────────────
# doc_type 매핑 (폴더 → 분류) — payload.doc_type 의 단일 정의
# ─────────────────────────────────────────────
DOC_TYPE_BY_FOLDER = {
    "kdigo": "clinical",  # KDIGO 공식 국제 가이드라인 (영문)
    "ksn_guideline": "clinical",  # 국내 임상 진료지침 (KSN 신장학회) + 영문 임상연구
    "knsn": "nutrition",  # 국문 영양·환자교육 (KSN 영양 + 질병관리청 바로알기)
    "nutrition": "nutrition",  # 직접 작성 영양 MD 문서 (칼륨·인 식품 분류 등)
    "lifestyle": "lifestyle",  # 생활습관 (운동·금연·절주·수면·스트레스)
}

# ─────────────────────────────────────────────
# 입력 형식 분기 (probe_headers 실측 기준)
#   PDF (16개): 영문·국문 모두 ## 헤더 추출 OK → MarkdownHeader 청킹
#   MD  (47개): ## 구조 전무(# 제목 1개씩) → MarkdownHeader 스킵, 제목 주입 + Recursive
# ─────────────────────────────────────────────
PDF_GLOBS = [
    # "kdigo/*.pdf",  # KDIGO 가이드라인 미반입(파일 없음, 인덱싱 0건) — 자료 추가 시 활성화
    "ksn_guideline/*.pdf",
    "knsn/*.pdf",
    "lifestyle/*.pdf",
]
MD_GLOBS = [
    "lifestyle/nosmokeguide/*.md",
    "lifestyle/alcohol/*.md",
    "lifestyle/sleep/*.md",
    "lifestyle/stress/*.md",
    "nutrition/*.md",  # 직접 작성 영양 MD (칼륨·인 식품 분류 등)
]

# ─────────────────────────────────────────────
# 언어 자동 판정 (payload.language) — 텍스트의 한글 음절 비율로 ko/en 결정 (2026-06-02)
#   의료 자료는 주 언어가 명확히 갈린다(영문 KDIGO 한글≈0% / 국문 자료 한글 다수)라
#   문서 앞부분 샘플의 한글:라틴 비율 하나로 robust 하게 판정한다.
#   → 영문/국문 어느 자료를 새로 넣어도 config 무수정 (EN_PDF_STEMS 하드코딩 폐지).
#     chunking.detect_language 가 이 두 상수를 공유한다.
# ─────────────────────────────────────────────
LANG_SAMPLE_CHARS = 3000  # 언어 판정에 쓸 문서 앞부분 글자 수
KO_LANG_THRESHOLD = 0.10  # 한글/(한글+라틴) ≥ 이 값이면 ko, 아니면 en

# ─────────────────────────────────────────────
# 인덱싱 제외 (파일명 부분문자열 매칭)
#   소아청소년편 = 타겟(40세+) 밖 / CKRT = 중환자 지속신대체요법 시술
#   신장학용어집 = 용어 정의만 있어 RAG 오검색 유발
# ─────────────────────────────────────────────
SKIP_FILE_SUBSTRINGS = [
    "소아청소년",  # 타겟(40세+) 밖
    "CKRT",  # 중환자 지속신대체요법 시술
    "신장학용어집",  # 용어 정의만 → RAG 오검색 유발
    "콩팥병 만화",  # 이미지 PDF — OCR 미처리 (0 chunk)
    "꼭 알아두어야 할 복지정보",  # 이미지 PDF — OCR 미처리 (0 chunk)
]
# 자료 개수는 하드코딩하지 않는다 (2026-06-02) — chunking.collect_pdfs 가 PDF_GLOBS 각각이
# 최소 1건 매치하는지(빈 폴더·glob 오타로 인한 조용한 누락 방지)만 검증하고, 실제 개수는
# 동적으로 센다. 자료가 늘어나는 운영을 위해 EXPECTED_RAW_PDF/EXPECTED_INDEXED_PDF 폐지.

# ─────────────────────────────────────────────
# 청킹 (Parent-Child 2단 — 06_chunking_strategy + PoC C단계 + probe)
# ─────────────────────────────────────────────
# PDF: MarkdownHeaderTextSplitter (# · ## 기준 / probe상 ###=0 이라 제외) → Recursive
MARKDOWN_HEADERS = [("#", "h1"), ("##", "h2")]
# Parent = 답변 맥락(넓음) / Child = 정밀 검색(좁음, 임베딩 대상)
PARENT_CHUNK_SIZE = 2000
PARENT_CHUNK_OVERLAP = 200
CHILD_CHUNK_SIZE = 400
CHILD_CHUNK_OVERLAP = 80
# Recursive 분할 separator (단락 우선) — 헤더 없는 MD/긴 섹션에 사용
RECURSIVE_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

# reference 번호 후처리 제거 (단위 동반 수치·권고번호는 chunking.py 에서 lookahead 보호)
STRIP_REFERENCES = True
# 보호 대상 예: "2,000mg"(단위), "Recommendation 3.3.1.1"(권고번호) → 제거 금지

# ─────────────────────────────────────────────
# Qdrant collection (parent 는 벡터X 텍스트 저장만 → dev/prod 분리 불요)
# ─────────────────────────────────────────────
COLLECTION_CHILD_DEV = "medical_kb_dev"  # child 벡터, embed-3-small 1536d
COLLECTION_CHILD_PROD = "medical_kb_prod"  # child 벡터, embed-3-large 3072d
COLLECTION_PARENT = "medical_kb_parents"  # parent (벡터 없음, parent_id 로 조회)

# ─────────────────────────────────────────────
# 임베딩 모델 정책 (project_api_model_policy)
#   small→large 변경 시 차원 1536→3072 → collection 재구축 필수
# ─────────────────────────────────────────────
EMBEDDING_MODEL_DEV = "text-embedding-3-small"
EMBEDDING_MODEL_PROD = "text-embedding-3-large"
EMBEDDING_DIM_DEV = 1536
EMBEDDING_DIM_PROD = 3072

# ─────────────────────────────────────────────
# age_group 태깅 (P1-4 — chunking_audit 2026-05-29) — 소아 콘텐츠 식별 규칙
#   타겟은 40세+ 성인 CKD. 소아 챕터는 드롭하지 않고 payload.age_group='pediatric' 으로
#   태깅(무손실)해 retriever 가 성인 서비스에서 age_group!=pediatric 으로 격리한다.
#   uploader(부착)·retriever(필터)가 이 규칙을 공유하는 단일 진실.
#     • KSN 국문 진료지침: source 가 KSN- 으로 시작하고 h2 에 '소아' 포함 (당뇨병 9장·고혈압 8장)
#     • KDIGO 영문: h2 에 pediatric/children/adolescent 포함 (성인 가이드라인 내 소아 섹션)
# ─────────────────────────────────────────────
PEDIATRIC_SOURCE_PREFIX = "KSN"
PEDIATRIC_H2_KEYWORD_KO = "소아"
PEDIATRIC_H2_KEYWORDS_EN = ("pediatric", "children", "adolescent")
AGE_GROUP_DEFAULT = "adult"
AGE_GROUP_PEDIATRIC = "pediatric"

# ─────────────────────────────────────────────
# track 태깅 (knsn/ 영양 3종 전용 — doc_type=nutrition)
#   파일명(source stem) 기반 파일 단위 판정.
#     "혈액투석 환자를 위한 영양..." → 파일 전체 hemodialysis
#     "복막투석 환자를 위한 영양..." → 파일 전체 peritoneal
#     "투석 전 단계의 만성콩팥병..." → 파일 전체 non_dialysis
#   h2 소제목이 달라져도 트랙이 바뀌지 않음 (교차 오염 방지).
#   clinical·lifestyle·기타 knsn 문서는 항상 common.
#   retriever 에서 "track=X OR track=common" OR 필터로 사용.
# ─────────────────────────────────────────────
TRACK_NON_DIALYSIS = "non_dialysis"
TRACK_HEMODIALYSIS = "hemodialysis"
TRACK_PERITONEAL = "peritoneal"
TRACK_DIALYSIS = "dialysis"  # 혈액·복막 구분 없는 투석 공통 (신규 — N.N.N 분할 결과)
TRACK_TRANSPLANT = "transplant"
TRACK_COMMON = "common"

# 파일명 부분 문자열 → track (doc_type=nutrition 파일에만 적용)
TRACK_BY_SOURCE_KO: dict = {
    "혈액투석": TRACK_HEMODIALYSIS,
    "혈액 투석": TRACK_HEMODIALYSIS,
    "복막투석": TRACK_PERITONEAL,
    "복막 투석": TRACK_PERITONEAL,
    "투석전": TRACK_NON_DIALYSIS,
    "투석 전": TRACK_NON_DIALYSIS,
    "비투석": TRACK_NON_DIALYSIS,
}

# 파일명 stem → track 강제 지정 (doc_type 우선도 무시 — clinical 파일 수동 트랙 지정용)
# 키: path.stem 완전일치 / 값: TRACK_* 상수
SOURCE_TRACK_OVERRIDE: dict = {
    "2021 적절한 혈액투석 치료 근거기반 진료지침": TRACK_HEMODIALYSIS,
    "(2012)복막투석 복막염 진료지침": TRACK_PERITONEAL,
}

# ─────────────────────────────────────────────
# Qdrant 업로드 (qdrant_uploader.py)
# ─────────────────────────────────────────────
QDRANT_DISTANCE = "Cosine"  # child 벡터 검색 거리 (정규화 임베딩 표준)
UPLOAD_BATCH_SIZE = 256  # upsert 배치 크기
# 로컬 스크립트 실행용 기본 URL (docker-compose 내부 호스트명 'qdrant' 가 아닌 localhost).
# env QDRANT_URL 이 있으면 그것을 우선한다.
QDRANT_LOCAL_URL = "http://localhost:6333"

# ─────────────────────────────────────────────
# payload 메타 스키마 (chunking.py 가 child/parent 에 부착, uploader 가 text·age_group 추가)
#   doc_type(폴더 기반)·source·section(헤더)·parent_id·hash·reference_removed
# ─────────────────────────────────────────────
PAYLOAD_FIELDS = [
    "doc_type",  # clinical | nutrition | lifestyle
    "source",  # 파일 stem (예: KDIGO-2024-CKD-Guideline)
    "language",  # ko | en
    "h1",
    "h2",  # MarkdownHeader 그룹 (MD는 frontmatter title → h1)
    "page",  # PDF 페이지 (가능 시)
    "parent_id",  # child → parent 조회 키
    "chunk_idx",
    "age_group",  # adult | pediatric (uploader 가 부착 — P1-4)
    "track",  # non_dialysis | hemodialysis | peritoneal | dialysis | common (chunking 단계 부착)
    "text",  # 원문 (uploader 가 부착 — 검색 결과 반환용)
]

# ─────────────────────────────────────────────
# N.N.N 분할 대상 (241212 진료지침 3개 섹션 전용)
#   chunk_pdf 이 이 섹션에 진입하면 N.N.N 항목별로 분할하고 항목 번호로 track을 부여.
#   나머지 청크는 무수정.
# ─────────────────────────────────────────────
SECTION_TRACK_SPLIT_SOURCE = "241212_당뇨병콩팥병 진료지침"
SECTION_TRACK_SPLIT_H2_PREFIXES = ("3.3.", "4.2.", "6.5.")
SECTION_ITEM_TRACK_MAP: dict = {
    "3.3.1": TRACK_NON_DIALYSIS,  # 투석 전 환자 HbA1c 목표 7% 미만
    "3.3.2": TRACK_COMMON,  # 개별화 기준 (트랙 무관)
    "3.3.3": TRACK_DIALYSIS,  # 투석 중 HbA1c 목표 불확실
    "4.2.1": TRACK_NON_DIALYSIS,  # 비투석 단백질 0.8 g/kg
    "4.2.2": TRACK_DIALYSIS,  # 투석 단백질 1.0–1.2 g/kg
    "6.5.1": TRACK_COMMON,  # 혈청지질검사 적응증 (트랙 무관)
    "6.5.2": TRACK_NON_DIALYSIS,  # 투석 전 스타틴 처방
    "6.5.3": TRACK_DIALYSIS,  # 투석 중 스타틴 신규처방 불필요
    "6.5.4": TRACK_DIALYSIS,  # 투석 시작 시 기존 스타틴 유지
}

# ─────────────────────────────────────────────
# 재현성
# ─────────────────────────────────────────────
SEED = 42
