"""임상 진료지침 chunk 중 비투석/투석 권고가 혼재된 것을 찾는 감사 스크립트.

조사 항목:
  1. Qdrant에서 doc_type=clinical, track=common chunk 중 혼재 패턴 검출
  2. 해당 PDF의 h3 헤더(###) 존재 여부 확인 (h3 분할 가능성)
  3. 혼재 chunk가 집중된 source·h2 목록 출력
"""

import os
import re
from collections import defaultdict
from pathlib import Path

env_file = Path(__file__).resolve().parents[2] / "envs" / ".local.env"
for ln in env_file.read_text(encoding="utf-8").splitlines():
    if "=" in ln and not ln.strip().startswith("#"):
        k, v = ln.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import FieldCondition, Filter, MatchValue  # noqa: E402

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
CHILD_COLL = "medical_kb_dev"
client = QdrantClient(url=QDRANT_URL)

# ── 혼재 패턴 키워드 ─────────────────────────────────────────────────────────
# "비투석 OR 투석 전" 권고가 있으면서 "투석 중 / 혈액투석 / 복막투석" 권고도 함께 있는 텍스트
NON_DIAL_PATS = re.compile(
    r"신대체요법을\s*받지\s*않|투석\s*전\s*단계|비투석|透析前|GFR.*[1-5]단계",
    re.IGNORECASE,
)
DIAL_PATS = re.compile(
    r"혈액투석|복막투석|투석\s*요법\s*중|투석\s*중인|투석\s*환자|HD|PD",
    re.IGNORECASE,
)
NUTRIENT_PATS = re.compile(
    r"단백질|칼륨|인\s*섭취|나트륨|칼슘|에너지|열량|탄수화물",
    re.IGNORECASE,
)

# ── doc_type=clinical, track=common chunk 전체 스캔 ──────────────────────────
print("Qdrant에서 doc_type=clinical & track=common 스캔 중...")
flt = Filter(
    must=[
        FieldCondition(key="doc_type", match=MatchValue(value="clinical")),
        FieldCondition(key="track", match=MatchValue(value="common")),
    ]
)

mixed: list[dict] = []  # 혼재 chunk
offset = None
scanned = 0

while True:
    result, next_offset = client.scroll(
        collection_name=CHILD_COLL,
        scroll_filter=flt,
        limit=256,
        offset=offset,
        with_payload=True,
    )
    if not result:
        break
    for pt in result:
        p = pt.payload or {}
        text = p.get("text", "")
        scanned += 1
        has_non_dial = bool(NON_DIAL_PATS.search(text))
        has_dial = bool(DIAL_PATS.search(text))
        has_nutrient = bool(NUTRIENT_PATS.search(text))
        if has_non_dial and has_dial and has_nutrient:
            mixed.append(
                {
                    "source": p.get("source", ""),
                    "h2": p.get("h2", ""),
                    "text": text,
                }
            )
    if next_offset is None:
        break
    offset = next_offset

print(f"스캔: {scanned}개 중 혼재 chunk {len(mixed)}개\n")

# ── 혼재 chunk를 source·h2 기준으로 그룹화 ─────────────────────────────────
groups: dict[str, list[str]] = defaultdict(list)
for c in mixed:
    key = f"{c['source']}  |  h2={c['h2'][:60]}"
    groups[key].append(c["text"])

print("=" * 70)
print(f"[혼재 chunk 그룹 — source | h2 기준]  ({len(groups)}개 그룹)")
print("=" * 70)
for grp_key, texts in sorted(groups.items()):
    print(f"\n  [{len(texts)}개] {grp_key}")
    # 첫 번째 chunk 원문 발췌 (투석 관련 수치 주변)
    sample = texts[0]
    for pat_str in ["0.8", "1.0", "1.2", "단백질", "칼륨", "인 섭취"]:
        idx = sample.find(pat_str)
        if idx >= 0:
            snippet = sample[max(0, idx - 80) : idx + 160].replace("\n", " ")
            print(f"     ▶ ...{snippet}...")
            break

# ── h3 헤더 존재 여부 확인 (PDF 원본에서) ────────────────────────────────────
print("\n" + "=" * 70)
print("[PDF 원본 h3 헤더(###) 존재 여부 확인]")
print("=" * 70)

# 혼재 chunk가 있는 source 파일들만 체크
sources_with_mixed = sorted({c["source"] for c in mixed})

import pymupdf4llm  # noqa: E402

try:
    from . import config as cfg
except ImportError:
    import config as cfg

H3_RE = re.compile(r"^###\s+(.+)", re.MULTILINE)
H2_RE = re.compile(r"^##\s+(.+)", re.MULTILINE)

for src in sources_with_mixed:
    # PDF 경로 탐색
    found_path = None
    for glob in cfg.PDF_GLOBS:
        folder = cfg.DATA_DIR / glob.replace("/*.pdf", "")
        for pdf in folder.glob("*.pdf"):
            if pdf.stem == src:
                found_path = pdf
                break
        if found_path:
            break
    if not found_path:
        print(f"\n  {src}: PDF 미발견")
        continue

    md = pymupdf4llm.to_markdown(str(found_path), pages=list(range(min(50, 300))))
    h3_headers = H3_RE.findall(md)
    h2_headers = H2_RE.findall(md)
    print(f"\n  {src}")
    print(f"    h2(##): {len(h2_headers)}개   h3(###): {len(h3_headers)}개")
    if h3_headers:
        print("    h3 샘플 (앞 10개):")
        for h in h3_headers[:10]:
            print(f"      ### {h}")
    else:
        print("    → h3 헤더 없음 — MarkdownHeaderTextSplitter ###분할 불가")
