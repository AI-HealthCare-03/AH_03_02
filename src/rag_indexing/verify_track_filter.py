"""track 필터 검증 + 0.8 g/kg 원문 확인."""
import os
from pathlib import Path

env_file = Path(__file__).resolve().parents[2] / "envs" / ".local.env"
for ln in env_file.read_text(encoding="utf-8").splitlines():
    if "=" in ln and not ln.strip().startswith("#"):
        k, v = ln.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
from openai import OpenAI

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
CHILD_COLL = "medical_kb_dev"

client = QdrantClient(url=QDRANT_URL)
oai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def embed(text: str) -> list[float]:
    return oai.embeddings.create(model="text-embedding-3-small", input=[text]).data[0].embedding

def search(query: str, track: str | None, top_k: int = 5):
    must = [FieldCondition(key="age_group", match=MatchValue(value="adult"))]
    if track:
        must.append(FieldCondition(key="track", match=MatchAny(any=[track, "common"])))
    hits = client.query_points(
        collection_name=CHILD_COLL,
        query=embed(query),
        limit=top_k,
        query_filter=Filter(must=must),
        with_payload=True,
    ).points
    return hits

# ── 문제1: "0.8 g/kg" 원문 확인 ─────────────────────────────────────────────
print("=" * 70)
print("[문제1] '0.8 g/kg' 단백질 원문 검색 (필터 없음, top_k=5)")
hits = search("단백질 하루 권장량 0.8 g/kg 만성콩팥병 비투석", track=None, top_k=5)
for i, h in enumerate(hits, 1):
    p = h.payload or {}
    print(f"\n  [{i}] score={h.score:.3f}  track={p.get('track')}  source={p.get('source')}")
    print(f"       h2={p.get('h2','')[:60]}")
    text = p.get("text", "")
    # 0.8 주변 문장 발췌
    idx = text.find("0.8")
    if idx >= 0:
        snippet = text[max(0, idx-100):idx+200]
        print(f"       ▶ ...{snippet}...")
    else:
        print(f"       ▶ {text[:200]}")

# ── 문제2: track 필터 on/off 비교 ────────────────────────────────────────────
print("\n" + "=" * 70)
print("[문제2] track 필터 비교 — '단백질 제한 만성콩팥병'")

for label, track in [("필터 없음(None)", None), ("hemodialysis", "hemodialysis"), ("non_dialysis", "non_dialysis")]:
    print(f"\n  ▶ {label}")
    hits = search("단백질 제한 만성콩팥병", track=track, top_k=5)
    for h in hits:
        p = h.payload or {}
        print(f"    score={h.score:.3f}  track={p.get('track'):20s}  source={p.get('source','')[:50]}")

print("\n" + "=" * 70)
