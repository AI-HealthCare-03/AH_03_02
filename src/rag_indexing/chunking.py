"""Phase 3 인덱싱 — Parent-Child 2단 청킹 (chunking.py).

학습카드 06_chunking_strategy + PoC C단계 실험(exp1_md_chunking) + 2026-05-29 RAG 심층점검
(probe_headers 실측: 모든 PDF는 ##헤더 OK / 47 MD는 ##헤더 전무) 기준으로 두 경로를 분기한다.

  • PDF 경로(16개 raw → SKIP 2개 제외 → 14개):
      pymupdf4llm.to_markdown → MarkdownHeaderTextSplitter(#·##) → parent(2000) → child(400)
  • MD 경로(47개 lifestyle):
      frontmatter 직접 파싱 + #제목을 h1 컨텍스트로 주입 → parent(2000) → child(400)
      (## 헤더가 없으므로 MarkdownHeaderTextSplitter 스킵)

검색은 child(400, 정밀·임베딩 대상), 답변 맥락은 parent(2000, 넓음)로 분리. child payload에
parent_id 를 부착해 검색 후 parent 를 끌어온다.

출력 (chunks/):
  • child_chunks.jsonl  — 임베딩 대상 (embedder.py 입력)
  • parent_chunks.jsonl — 벡터 없이 parent_id 조회용 (qdrant_uploader.py 입력)

키·Docker·Qdrant 불요. 실행 (의존성은 poc/.venv 에 설치돼 있음):
    cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/poc
    source .venv/bin/activate
    python ../src/rag_indexing/chunking.py            # 전체 인덱싱 → JSONL 덤프
    python ../src/rag_indexing/chunking.py --dry-run   # 통계만, 파일 미출력
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf4llm
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

# config 는 같은 패키지. 패키지 import·직접 실행 둘 다 지원.
try:
    from . import config as cfg
except ImportError:
    import config as cfg


# ─────────────────────────────────────────────────────────────────────────────
# 분할기 (config 상수 기반 — 단일 진실)
# ─────────────────────────────────────────────────────────────────────────────
_md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=cfg.MARKDOWN_HEADERS)
_parent_splitter = RecursiveCharacterTextSplitter(
    chunk_size=cfg.PARENT_CHUNK_SIZE,
    chunk_overlap=cfg.PARENT_CHUNK_OVERLAP,
    separators=cfg.RECURSIVE_SEPARATORS,
)
_child_splitter = RecursiveCharacterTextSplitter(
    chunk_size=cfg.CHILD_CHUNK_SIZE,
    chunk_overlap=cfg.CHILD_CHUNK_OVERLAP,
    separators=cfg.RECURSIVE_SEPARATORS,
)

_MIN_CHUNK_CHARS = 20  # 헤더만 남은 빈 그룹·공백 청크 제거 기준


# ─────────────────────────────────────────────────────────────────────────────
# 노이즈 child 필터 (2026-06-15 감사 기반 — 10,709청크 중 117건 제거)
# ① URL/저작권 파편  ② 참고문헌·검색식 파편  ④ 표지 반복
# short(≤63자) 509건은 이 필터 대상 외 (정상 정의문·수치 혼재)
# ─────────────────────────────────────────────────────────────────────────────
_NOISE_COPYRIGHT = re.compile(
    r"저작권.*https?://"
    r"|무단\s*이용.{0,30}법적책임"
    r"|외부\s*저작권자",
    re.DOTALL,
)
_NOISE_URL_DOMINANT = re.compile(r"^[\s\-\d\.\)]*https?://\S+[\s\S]{0,80}$")
_NOISE_REF_ITEM = re.compile(
    r"^\s*\[?\d{1,3}\]?\s+\w[\w\s,\.\-]{0,60}"
    r"(?:https?://|doi:|doi\.org|J\s+\w|JAMA|N\s*Engl|Lancet|BMJ|Kidney\s+Int"
    r"|Nephrol|Clin\s+J\s+Am\s+Soc|Am\s+J\s+Kidney|JASN)",
    re.IGNORECASE,
)
_NOISE_SEARCH_QUERY = re.compile(
    r"^\s*\d+\s+(?:exp\s+)?[\w\s\/\(\)]+\/\s*\d{3,}",
    re.MULTILINE,
)
_NOISE_COVER_ONLY = re.compile(r"^\s*\*{0,2}[\w\s()가-힣]+진료지침\*{0,2}\s*\n\s*\*{0,2}[\w\s()A-Za-z]+\*{0,2}\s*$")


def _is_noise_child(text: str) -> bool:
    """URL 파편·참고문헌·검색식 등 임베딩 불요 child인지 판정.

    True → _emit_parent_children에서 child 스킵 (parent는 유지 — 참조 무결성 보존).
    본문이 있는 경계 케이스(통계표 파편, 본문+URL 잘림)는 False — 수동 삭제 대상.
    """
    t = text.strip()
    if not t:
        return False
    if _NOISE_COPYRIGHT.search(t):
        return True
    if _NOISE_URL_DOMINANT.match(t) and len(t) < 200:
        return True
    if _NOISE_REF_ITEM.search(t) and len(t) < 300:
        return True
    lines = t.splitlines()
    if len(lines) >= 2 and all(_NOISE_SEARCH_QUERY.match(ln) for ln in lines if ln.strip()):
        return True
    if _NOISE_COVER_ONLY.match(t) and len(t) < 120:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# reference 번호 제거 (단위·소수점 권고번호 보호)
# ─────────────────────────────────────────────────────────────────────────────
# 영문 임상 PDF에서 pymupdf4llm 변환 시 본문에 섞이는 상위첨자형 인용번호를 제거한다.
# 예: "...progression.453,454 In addition..." → "...progression. In addition..."
# 보호: 단위 동반 수치(2,000 mg), 소수점 권고번호(Recommendation 3.3.1.1), 연도(2024)는 건드리지 않음.
#   - 문장부호/소문자 직후 즉시 붙은, 콤마·하이픈으로 연결된 3~4자리 숫자 클러스터만 대상.
#   - 뒤에 단위/소수점이 오면(negative lookahead) 제외.
_UNIT_AHEAD = r"(?!\s*(?:mg|g|kg|mL|ml|L|mmol|mEq|mmHg|%|kcal|단계|점|회|일|주|개월|년|명))"
_REF_CLUSTER = re.compile(
    r"(?<=[a-z\).,])"  # 직전: 소문자/닫는괄호/문장부호 (단어에 붙은 인용)
    r"\d{1,4}(?:[,–\-]\d{1,4})+"  # 콤마·en대시·하이픈으로 연결된 숫자 2개 이상
    r"(?![.\d])" + _UNIT_AHEAD  # 직후 소수점/숫자 아님 (권고번호·연도 보호)
)
# 브라켓형 인용 (pymupdf4llm 이 상위첨자 인용을 [91]·[91][,][93]·[12][§] 로 변환 — 2026-05-29 점검 P0-3)
#   • clean_markdown 이 먼저 "m[2]"→"m²" 로 단위를 보호하므로 여기서 [2] 충돌 없음.
#   • [†‡§] 각주 마커 브라켓도 함께 제거. CKD 단계(G1)·권고번호(3.3.1)는 브라켓 없어 안전.
_REF_BRACKET = re.compile(
    r"\[\d{1,4}\](?:\s*\[[,–\-]\]\s*\[\d{1,4}\])*"  # [91] 또는 [91][,][93]
    r"|\[[†‡§]\]"  # [†] [‡] [§] 각주 마커
)


def strip_references(text: str) -> str:
    """본문에 섞인 상위첨자 인용(콤마형·브라켓형)을 제거 (단위·권고번호·연도 보호)."""
    if not cfg.STRIP_REFERENCES:
        return text
    cleaned = _REF_CLUSTER.sub("", text)
    cleaned = _REF_BRACKET.sub("", cleaned)
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# pymupdf4llm 변환 노이즈 정리 (PDF 경로 전용 — 변환 직후, 헤더 분할 전)
# ─────────────────────────────────────────────────────────────────────────────
# pymupdf4llm 은 이미지를 자리표시자 마커로 남긴다. 임베딩 대상인 child 를 오염시키므로
# 마커는 제거하되 OCR 추출된 picture text 내용(영양 자료 제목 등)은 보존한다.
#   • "**==> picture [438 x 237] intentionally omitted <==**" → 완전 제거 (내용 없음)
#   • "**----- Start/End of picture text -----**" → 마커만 제거 (내부 텍스트 보존)
#   • "<br>" → 개행 (영양 자료의 줄바꿈)
_PICTURE_OMITTED = re.compile(r"\*\*==>\s*picture\b[^\n]*?omitted\s*<==\*\*")
_PICTURE_TEXT_MARKER = re.compile(r"\*\*-+\s*(?:Start|End) of picture text\s*-+\*\*")

# 인코딩 깨짐 복원 (2026-05-29 점검 P0-1 — 실측 검증된 매핑만)
#   • "m[2]" → "m²"  (eGFR 단위 1.73 m², 모든 출처 313개)
#   • "$"/"‡" + 숫자(천단위 콤마 달러 제외) → "≥"  ("$180 mm Hg"·"‡75 years" = ≥, "$1,571" = 달러 보존)
#     ⚠ synthesis 권고($→≤·‡→≥)는 원본 대조 결과 틀림 — 둘 다 문맥상 ≥, 각주/달러는 보존해야 함.
_GEQ_GLYPH = re.compile(r"[‡$](?=\d)(?!\d{0,2},\d{3})")


def clean_markdown(md: str) -> str:
    """pymupdf4llm 변환 마크다운에서 이미지 자리표시자·인코딩 깨짐 노이즈를 제거."""
    md = _PICTURE_OMITTED.sub("", md)
    md = _PICTURE_TEXT_MARKER.sub("", md)
    md = md.replace("<br>", "\n")
    md = md.replace("m[2]", "m²")  # P0-1 단위 (브라켓 인용 제거보다 먼저 — [2] 보호)
    md = _GEQ_GLYPH.sub("≥", md)  # P0-1 부등호 복원 (달러·각주 보존)
    md = md.replace("\xa0", " ")  # non-breaking space → 일반 공백
    md = re.sub(r"[ \t]{2,}", " ", md)
    md = re.sub(r"\n{3,}", "\n\n", md)  # P1-3 과도한 개행 정규화
    return md


# ─────────────────────────────────────────────────────────────────────────────
# MD scrape 아티팩트 정리 (MD 경로 전용 — 2026-05-29 점검 P0-2)
# ─────────────────────────────────────────────────────────────────────────────
# mentalhealth/bgnmh 스크랩 MD 본문에 UI 텍스트('선택됨'·'질환 정보 모두 펼치기' 등)가 섞임.
# PDF용 clean_markdown 은 MD 경로에서 호출되지 않았던 누락을 보강한다.
_MD_UI_ARTIFACT = re.compile(r"(질환 정보 모두 펼치기|정보 모두 펼치기|모두 펼치기|모두 접기|선택됨|펼치기|접기)")


def clean_md_scrape_artifacts(text: str) -> str:
    """MD 본문에서 스크랩 UI 텍스트·nbsp·과도 개행을 제거."""
    text = text.replace("\xa0", " ")
    text = _MD_UI_ARTIFACT.sub("", text)
    text = text.replace("<br>", "\n")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────────────────────────────────────────
def _doc_type_for(path: Path) -> str:
    """data/ 하위 최상위 폴더로 doc_type 판정."""
    folder = path.relative_to(cfg.DATA_DIR).parts[0]
    return cfg.DOC_TYPE_BY_FOLDER[folder]


def detect_language(text: str) -> str:
    """텍스트 앞부분의 한글:라틴 글자 비율로 ko/en 자동 판정 (config 상수 단일 진실).

    의료 자료는 주 언어가 명확히 갈려(영문 KDIGO 한글≈0% / 국문 자료 한글 다수)
    문서 선두 샘플의 비율 하나로 robust 하다. 숫자·기호·공백은 분모에서 제외하고
    한글 음절(가-힣)과 라틴 알파벳만 센다. 글자가 전혀 없으면 보수적으로 ko.
    → 영문/국문 어느 자료를 새로 넣어도 config 무수정 (EN_PDF_STEMS 하드코딩 폐지, 2026-06-02).
    """
    sample = text[: cfg.LANG_SAMPLE_CHARS]
    hangul = latin = 0
    for ch in sample:
        if "가" <= ch <= "힣":
            hangul += 1
        elif ch.isascii() and ch.isalpha():
            latin += 1
    total = hangul + latin
    if total == 0:
        return "ko"
    return "ko" if hangul / total >= cfg.KO_LANG_THRESHOLD else "en"


def _is_skipped(path: Path) -> bool:
    return any(sub in path.name for sub in cfg.SKIP_FILE_SUBSTRINGS)


def _track_for(doc_type: str, source: str) -> str:
    """파일명(source stem) 기반 파일 단위 트랙 판정.

    nutrition 문서 중 트랙 키워드가 파일명에 있으면 해당 트랙.
    파일 전체에 동일 트랙을 적용하므로 h2 소제목 변경에 흔들리지 않고
    비교 섹션 h2로 인한 교차 오염도 방지된다.
    clinical·lifestyle·기타 knsn 은 항상 common.
    SOURCE_TRACK_OVERRIDE 에 등록된 파일은 doc_type 무관하게 강제 지정.
    """
    if source in cfg.SOURCE_TRACK_OVERRIDE:
        return cfg.SOURCE_TRACK_OVERRIDE[source]
    if doc_type != "nutrition":
        return cfg.TRACK_COMMON
    for keyword, track in cfg.TRACK_BY_SOURCE_KO.items():
        if keyword in source:
            return track
    return cfg.TRACK_COMMON


# ─────────────────────────────────────────────────────────────────────────────
# N.N.N 항목 분할 (241212 진료지침 3개 섹션 전용)
# ─────────────────────────────────────────────────────────────────────────────
# "- 4.2.1." / "- 6.5.3." 등 행 선두의 번호 항목을 감지하는 패턴
_ITEM_BOUNDARY_RE = re.compile(r"(?:^|\n)(\s*-\s*\d+\.\d+\.\d+\.)", re.MULTILINE)
_ITEM_NO_RE = re.compile(r"^\s*-\s*(\d+\.\d+\.\d+)\.")
# 권고문 문장 끝(마침표 + 선택적 공백 + 줄바꿈) 감지 — 이후 텍스트는 근거 서술
# (?!\s*-) : 다음 줄이 또 다른 항목(- N.N.N.)이면 제외
_REC_END_RE = re.compile(r"\.\s*\n(?!\s*-)")


def _item_track_for(text: str) -> str:
    """텍스트 첫 행의 N.N.N 번호로 track 결정. 매핑에 없으면 common."""
    m = _ITEM_NO_RE.match(text.lstrip())
    if m:
        return cfg.SECTION_ITEM_TRACK_MAP.get(m.group(1), cfg.TRACK_COMMON)
    return cfg.TRACK_COMMON


def _emit_split_numbered_section(
    *,
    parents: list,
    children: list,
    text: str,
    source: str,
    doc_type: str,
    language: str,
    h1: str,
    h2: str,
    parent_counter: list,
    page: int | None = None,
) -> None:
    """N.N.N 번호 기반 항목 분할 + 트랙 태깅.

    "- N.N.N." 패턴 위치를 경계로 텍스트를 항목별로 나눈다.
    번호 없는 서술부(preamble/narrative)는 common 폴백.
    N.N.N. 패턴이 없는 청크(설명 서술)도 common으로 통과.
    """
    boundaries = [m.start() for m in _ITEM_BOUNDARY_RE.finditer(text)]

    if not boundaries:
        # N.N.N. 없음 → common 폴백
        _emit_parent_children(
            parents=parents,
            children=children,
            text=text,
            source=source,
            doc_type=doc_type,
            language=language,
            h1=h1,
            h2=h2,
            parent_counter=parent_counter,
            page=page,
            track=cfg.TRACK_COMMON,
        )
        return

    # 첫 번째 항목 이전 서술 (preamble)
    if boundaries[0] > 0:
        preamble = text[: boundaries[0]].strip()
        if len(preamble) >= _MIN_CHUNK_CHARS:
            _emit_parent_children(
                parents=parents,
                children=children,
                text=preamble,
                source=source,
                doc_type=doc_type,
                language=language,
                h1=h1,
                h2=h2,
                parent_counter=parent_counter,
                page=page,
                track=cfg.TRACK_COMMON,
            )

    # 각 N.N.N 항목
    for i, pos in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
        # boundary가 '\n'으로 시작하면 그 문자를 건너뜀
        item_start = pos + 1 if text[pos] == "\n" else pos
        item_text = text[item_start:end].strip()
        if len(item_text) < _MIN_CHUNK_CHARS:
            continue
        item_track = _item_track_for(item_text)
        # 권고문 뒤에 붙은 근거 서술을 common으로 분리
        # 권고문은 첫 문장(마침표 + \n)으로 끝남. 이후 서술은 track 무관 근거 텍스트.
        para_m = _REC_END_RE.search(item_text, 20)  # 최소 20자 이후(항목 마커 스킵)
        if para_m and len(item_text[para_m.end() :].strip()) >= _MIN_CHUNK_CHARS:
            head = item_text[: para_m.start() + 1].strip()  # 마침표 포함
            tail = item_text[para_m.end() :].strip()
            if len(head) >= _MIN_CHUNK_CHARS:
                _emit_parent_children(
                    parents=parents,
                    children=children,
                    text=head,
                    source=source,
                    doc_type=doc_type,
                    language=language,
                    h1=h1,
                    h2=h2,
                    parent_counter=parent_counter,
                    page=page,
                    track=item_track,
                )
            _emit_parent_children(
                parents=parents,
                children=children,
                text=tail,
                source=source,
                doc_type=doc_type,
                language=language,
                h1=h1,
                h2=h2,
                parent_counter=parent_counter,
                page=page,
                track=cfg.TRACK_COMMON,
            )
        else:
            _emit_parent_children(
                parents=parents,
                children=children,
                text=item_text,
                source=source,
                doc_type=doc_type,
                language=language,
                h1=h1,
                h2=h2,
                parent_counter=parent_counter,
                page=page,
                track=item_track,
            )


def _parent_id(source: str, h1: str, h2: str, idx: int) -> str:
    """source+헤더+parent 순번으로 결정적 parent_id 생성."""
    key = f"{source}|{h1}|{h2}|{idx}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _child_id(parent_id: str, idx: int) -> str:
    return hashlib.sha1(f"{parent_id}|{idx}".encode()).hexdigest()[:16]


def _emit_parent_children(
    *,
    parents: list,
    children: list,
    text: str,
    source: str,
    doc_type: str,
    language: str,
    h1: str,
    h2: str,
    parent_counter: list,
    page: int | None = None,
    track: str = cfg.TRACK_COMMON,
) -> None:
    """한 섹션 텍스트를 parent(2000)→child(400)로 분할해 두 리스트에 누적.

    parent_counter 는 [int] 단일원소 리스트 (문서 전체에서 parent 순번을 이어붙이기 위한 가변 카운터).
    page 는 PDF 페이지 번호 (page_chunks 경로에서 전달, MD 는 None).
    """
    text = strip_references(text).strip()
    if len(text) < _MIN_CHUNK_CHARS:
        return
    for parent_text in _parent_splitter.split_text(text):
        parent_text = parent_text.strip()
        if len(parent_text) < _MIN_CHUNK_CHARS:
            continue
        pidx = parent_counter[0]
        parent_counter[0] += 1
        pid = _parent_id(source, h1, h2, pidx)
        parents.append(
            {
                "id": pid,
                "text": parent_text,
                "payload": {
                    "doc_type": doc_type,
                    "source": source,
                    "language": language,
                    "h1": h1,
                    "h2": h2,
                    "track": track,
                },
            }
        )
        for cidx, child_text in enumerate(_child_splitter.split_text(parent_text)):
            child_text = child_text.strip()
            if len(child_text) < _MIN_CHUNK_CHARS:
                continue
            if _is_noise_child(child_text):
                continue
            children.append(
                {
                    "id": _child_id(pid, cidx),
                    "text": child_text,
                    "payload": {
                        "doc_type": doc_type,
                        "source": source,
                        "language": language,
                        "h1": h1,
                        "h2": h2,
                        "page": page,  # PDF 페이지 (page_chunks 경로) / MD 는 None
                        "parent_id": pid,
                        "chunk_idx": cidx,
                        "track": track,
                    },
                }
            )


# ─────────────────────────────────────────────────────────────────────────────
# PDF 경로 — pymupdf4llm → MarkdownHeader(#·##) → Parent-Child
# ─────────────────────────────────────────────────────────────────────────────
def chunk_pdf(path: Path) -> tuple[list, list]:
    source = path.stem
    doc_type = _doc_type_for(path)
    file_track = _track_for(doc_type, source)  # 파일 단위 트랙 — 루프 내에서 불변

    # page_chunks=True → 페이지별 {text, metadata.page_number}. 페이지 경계를 넘는 헤더는
    # carry-over(직전 h1/h2 상속)로 self-contained 맥락을 유지하면서 page 를 부착한다.
    # (KDIGO 영문은 # 헤더가 0개라 h1 은 대부분 공백 — 상속으로 페이지 선두 텍스트 맥락 보강)
    pages = pymupdf4llm.to_markdown(str(path), page_chunks=True, show_progress=False)

    # 언어: 앞 페이지들의 텍스트를 모아 한글 비율로 자동 판정 (stem 하드코딩 폐지)
    head_text = "".join(pg.get("text", "") for pg in pages[:5])
    language = detect_language(head_text)

    parents: list = []
    children: list = []
    parent_counter = [0]
    last_h1, last_h2 = "", ""
    for pg in pages:
        page_no = pg.get("metadata", {}).get("page_number")
        page_md = clean_markdown(pg.get("text", ""))
        if not page_md.strip():
            continue
        for grp in _md_splitter.split_text(page_md):
            g_h1 = grp.metadata.get("h1", "")
            g_h2 = grp.metadata.get("h2", "")
            if g_h1:
                last_h1, last_h2 = g_h1, ""  # 새 h1 등장 → 하위 h2 리셋
            if g_h2:
                last_h2 = g_h2
            effective_h2 = g_h2 or last_h2
            # 241212 진료지침 3개 섹션(3.3/4.2/6.5)은 N.N.N 항목별 분할 + 트랙 태깅
            if source == cfg.SECTION_TRACK_SPLIT_SOURCE and any(
                effective_h2.startswith(p) for p in cfg.SECTION_TRACK_SPLIT_H2_PREFIXES
            ):
                _emit_split_numbered_section(
                    parents=parents,
                    children=children,
                    text=grp.page_content,
                    source=source,
                    doc_type=doc_type,
                    language=language,
                    h1=g_h1 or last_h1,
                    h2=effective_h2,
                    parent_counter=parent_counter,
                    page=page_no,
                )
            else:
                _emit_parent_children(
                    parents=parents,
                    children=children,
                    text=grp.page_content,
                    source=source,
                    doc_type=doc_type,
                    language=language,
                    h1=g_h1 or last_h1,
                    h2=effective_h2,
                    parent_counter=parent_counter,
                    page=page_no,
                    track=file_track,  # 파일 단위 고정값 — h2 소제목에 흔들리지 않음
                )
    return parents, children


# ─────────────────────────────────────────────────────────────────────────────
# MD 경로 — frontmatter 파싱 + #제목 h1 주입 → Parent-Child (MarkdownHeader 스킵)
# ─────────────────────────────────────────────────────────────────────────────
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """polymorphic YAML frontmatter 를 평면 dict 로 파싱하고 본문을 반환.

    nosmokeguide: dataId/title/category/source/source_url/writer/writeDate/license/keywords
    alcohol·sleep·stress: title/category/source/source_url/license
    공통 키만 신뢰하므로 단순 key: value 파싱으로 충분 (중첩·리스트 없음).
    """
    lines = text.splitlines()
    meta: dict = {}
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            for ln in lines[1:end]:
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip()] = v.strip()
            return meta, "\n".join(lines[end + 1 :])
    return meta, text


def _strip_leading_title(body: str) -> tuple[str, str]:
    """본문 첫 '# 제목' 줄을 떼어내 (제목, 나머지본문) 반환. 없으면 ('', body)."""
    lines = body.splitlines()
    title = ""
    start = 0
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        m = re.match(r"^#\s+(.*\S)\s*$", ln)
        if m:
            title = m.group(1).strip()
            start = i + 1
        break
    return title, "\n".join(lines[start:])


def chunk_md(path: Path) -> tuple[list, list]:
    source = path.stem
    doc_type = _doc_type_for(path)

    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    body = clean_md_scrape_artifacts(body)  # P0-2: UI 텍스트·nbsp 제거 (제목 분리 전)
    title_from_body, body = _strip_leading_title(body)
    language = detect_language(body)  # 본문 한글 비율로 자동 판정 (lifestyle MD 는 사실상 ko)
    # h1 = frontmatter title 우선, 없으면 본문 # 제목. (probe상 MD는 # 1개씩 존재)
    h1 = meta.get("title") or title_from_body
    # h2 = frontmatter category (절주/수면/스트레스/금연방법 등) — 섹션 컨텍스트 보강
    h2 = meta.get("category", "")

    parents: list = []
    children: list = []
    parent_counter = [0]
    _emit_parent_children(
        parents=parents,
        children=children,
        text=body,
        source=source,
        doc_type=doc_type,
        language=language,
        h1=h1,
        h2=h2,
        parent_counter=parent_counter,
        track=_track_for(doc_type, source),  # lifestyle MD → 항상 common
    )
    return parents, children


# ─────────────────────────────────────────────────────────────────────────────
# 파일 수집
# ─────────────────────────────────────────────────────────────────────────────
def collect_pdfs() -> tuple[list[Path], list[Path]]:
    """PDF 수집 → (indexed, skipped) 반환.

    개수를 하드코딩하지 않고 PDF_GLOBS 각각이 최소 1건 매치하는지만 검증한다 (빈 폴더·glob
    오타로 인한 조용한 누락 방지). 실제 개수는 동적으로 센다 — 자료 추가 시 config 무수정.
    """
    found: list[Path] = []
    empty_globs: list[str] = []
    for g in cfg.PDF_GLOBS:
        matches = sorted(cfg.DATA_DIR.glob(g))
        if not matches:
            empty_globs.append(g)
        found.extend(matches)
    assert not empty_globs, f"매치 0건인 PDF_GLOB: {empty_globs} — data/ 폴더·경로·glob 오타 확인 (자료 누락 방지)."
    skipped = [p for p in found if _is_skipped(p)]
    indexed = [p for p in found if not _is_skipped(p)]
    return indexed, skipped


def collect_mds() -> list[Path]:
    found: list[Path] = []
    for g in cfg.MD_GLOBS:
        found.extend(sorted(cfg.DATA_DIR.glob(g)))
    return found


# ─────────────────────────────────────────────────────────────────────────────
# JSONL 덤프
# ─────────────────────────────────────────────────────────────────────────────
def dump_jsonl(rows: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Parent-Child 청킹 → JSONL 덤프")
    parser.add_argument("--dry-run", action="store_true", help="통계만 출력, 파일 미생성")
    args = parser.parse_args()

    pdfs, skipped = collect_pdfs()
    mds = collect_mds()
    print(f"입력: PDF {len(pdfs)}개 (raw {len(pdfs) + len(skipped)} − SKIP {len(skipped)}) + MD {len(mds)}개")
    for p in skipped:
        print(f"  [SKIP] {p.relative_to(cfg.DATA_DIR)}  (SKIP_FILE_SUBSTRINGS)")

    all_parents: list = []
    all_children: list = []

    print("\n[PDF 경로] pymupdf4llm → MarkdownHeader(#·##) → Parent-Child")
    for p in pdfs:
        parents, children = chunk_pdf(p)
        all_parents.extend(parents)
        all_children.extend(children)
        lang = parents[0]["payload"]["language"] if parents else "?"
        tracks = sorted({c["payload"].get("track", "?") for c in children})
        print(f"  {p.stem:52s} [{lang}] parent={len(parents):4d} child={len(children):5d} tracks={tracks}")

    print("\n[MD 경로] frontmatter + #제목 주입 → Parent-Child")
    md_parent_n = md_child_n = 0
    for p in mds:
        parents, children = chunk_md(p)
        all_parents.extend(parents)
        all_children.extend(children)
        md_parent_n += len(parents)
        md_child_n += len(children)
    print(f"  MD {len(mds)}개 합계: parent={md_parent_n} child={md_child_n}")

    # 무결성: 모든 child.parent_id 가 parent.id 에 존재
    parent_ids = {p["id"] for p in all_parents}
    orphans = [c for c in all_children if c["payload"]["parent_id"] not in parent_ids]
    assert not orphans, f"고아 child {len(orphans)}개 — parent_id 무결성 위반"

    print("\n" + "=" * 60)
    print(f"총 parent {len(all_parents)}개 / child {len(all_children)}개 (고아 0)")
    by_type: dict = {}
    for c in all_children:
        by_type[c["payload"]["doc_type"]] = by_type.get(c["payload"]["doc_type"], 0) + 1
    print(f"child doc_type 분포: {by_type}")

    by_track: dict = {}
    for c in all_children:
        t = c["payload"].get("track", "?")
        by_track[t] = by_track.get(t, 0) + 1
    print(f"child track  분포: {by_track}")

    soah_h2 = [
        c["payload"].get("h2", "")
        for c in all_children
        if "소아" in (c["payload"].get("h2") or "")
        or any(kw in (c["payload"].get("h2") or "").lower() for kw in ("pediatric", "children", "adolescent"))
    ]
    print(f"소아 관련 h2 child: {len(soah_h2)}개 (0 예상) {soah_h2[:3] if soah_h2 else ''}")

    if args.dry_run:
        print("\n--dry-run: 파일 미생성")
        return

    child_path = cfg.CHUNKS_DIR / "child_chunks.jsonl"
    parent_path = cfg.CHUNKS_DIR / "parent_chunks.jsonl"
    dump_jsonl(all_children, child_path)
    dump_jsonl(all_parents, parent_path)
    print(f"\n덤프 완료:\n  {child_path}\n  {parent_path}")


if __name__ == "__main__":
    main()
