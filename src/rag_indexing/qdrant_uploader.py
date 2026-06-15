"""Phase 3 인덱싱 — Qdrant 업로드 (qdrant_uploader.py).

embedder.py 산출물 chunks/embedded_child_chunks.jsonl(벡터 포함)과 chunking.py 의
chunks/parent_chunks.jsonl 을 두 collection 으로 업로드한다.

  • child  → medical_kb_dev (벡터 1536d, Cosine)   ─ 정밀 검색 대상
  • parent → medical_kb_parents (벡터 없음)         ─ child.parent_id 로 retrieve 만

업로드 직전 두 가지 후처리를 적용한다 (2026-05-29 chunking 적대점검 P1-4·P1-5):
  • age_group 태깅(P1-4): KSN 소아 챕터·KDIGO 소아 섹션을 'pediatric' 으로 태깅(무손실).
    드롭하지 않고 retriever 가 성인 서비스에서 격리한다. 규칙은 config 단일 진실.
  • text-hash dedup(P1-5): child 의 정확 중복 텍스트를 첫 등장만 남기고 제거(권고문 중복 등).
    parent 는 parent_id 참조 무결성을 위해 dedup 하지 않는다.

Qdrant point id 는 정수/UUID 만 허용하므로 16-hex chunk id 를 int(hex,16)(u64)로 변환하고
payload 에 원본 chunk_id 를 보존한다. parent 조회는 int(parent_id,16) 로 일관 변환한다.

실행 (poc/.venv 에 qdrant-client 설치 필요 — `uv pip install qdrant-client` 또는 rag 그룹):
    cd .../poc && source .venv/bin/activate
    docker compose up -d qdrant                          # 대시보드 http://localhost:6333/dashboard
    python ../src/rag_indexing/qdrant_uploader.py --recreate         # collection 재생성 후 전체 업로드
    python ../src/rag_indexing/qdrant_uploader.py --dry-run          # Qdrant 없이 태깅·dedup·id 통계만
    python ../src/rag_indexing/qdrant_uploader.py --child-only --limit 100
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

try:
    from . import config as cfg
except ImportError:
    import config as cfg


# ─────────────────────────────────────────────────────────────────────────────
# point id 변환 — 16-hex chunk id → u64 정수 (Qdrant 허용 형식)
# ─────────────────────────────────────────────────────────────────────────────
def point_id(hex_id: str) -> int:
    """16자리 hex chunk id 를 결정적 u64 정수 point id 로 변환 (무손실 양방향)."""
    return int(hex_id, 16)


# ─────────────────────────────────────────────────────────────────────────────
# age_group 태깅 (P1-4) — config 규칙 단일 진실 (uploader 부착, retriever 필터)
# ─────────────────────────────────────────────────────────────────────────────
def age_group_for(payload: dict) -> str:
    """payload 의 source·h2 로 소아 콘텐츠 여부 판정. 기본 adult."""
    h2 = payload.get("h2", "") or ""
    source = payload.get("source", "") or ""
    if source.startswith(cfg.PEDIATRIC_SOURCE_PREFIX) and cfg.PEDIATRIC_H2_KEYWORD_KO in h2:
        return cfg.AGE_GROUP_PEDIATRIC
    if cfg.PEDIATRIC_H2_KEYWORD_KO in h2:
        return cfg.AGE_GROUP_PEDIATRIC
    h2_lower = h2.lower()
    if any(k in h2_lower for k in cfg.PEDIATRIC_H2_KEYWORDS_EN):
        return cfg.AGE_GROUP_PEDIATRIC
    return cfg.AGE_GROUP_DEFAULT


# ─────────────────────────────────────────────────────────────────────────────
# text-hash dedup (P1-5) — child 정확 중복 제거 (첫 등장 유지, 순서 보존)
# ─────────────────────────────────────────────────────────────────────────────
def dedup_children(children: list[dict]) -> tuple[list[dict], int]:
    """child 의 text 정확 일치 중복을 첫 등장만 남기고 제거. (남은 리스트, 제거 수)."""
    seen: set[str] = set()
    kept: list[dict] = []
    removed = 0
    for c in children:
        h = hashlib.sha256(c["text"].encode("utf-8")).hexdigest()
        if h in seen:
            removed += 1
            continue
        seen.add(h)
        kept.append(c)
    return kept, removed


# ─────────────────────────────────────────────────────────────────────────────
# payload 조립 — 원본 payload + age_group + text + 원본 chunk_id 보존
# ─────────────────────────────────────────────────────────────────────────────
def build_payload(row: dict) -> dict:
    payload = dict(row["payload"])
    payload["age_group"] = age_group_for(payload)
    payload["text"] = row["text"]
    payload["chunk_id"] = row["id"]  # 원본 16-hex (point id 는 정수 변환되므로 보존)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# JSONL I/O (embedder.py 와 동일 — 두 사용처가 됐으므로 향후 io.py 승격 후보)
# ─────────────────────────────────────────────────────────────────────────────
def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Qdrant 클라이언트 (lazy — dry-run 은 client 불요)
# ─────────────────────────────────────────────────────────────────────────────
def make_client(url: str | None = None):
    from qdrant_client import QdrantClient

    url = url or os.getenv("QDRANT_URL") or cfg.QDRANT_LOCAL_URL
    return QdrantClient(url=url)


def ensure_child_collection(client, name: str, dim: int, *, recreate: bool) -> None:
    from qdrant_client.models import Distance, VectorParams

    if recreate and client.collection_exists(name):
        client.delete_collection(name)
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def ensure_parent_collection(client, name: str, *, recreate: bool) -> None:
    """parent 는 검색하지 않으므로 벡터 없는(payload-only) collection 으로 생성."""
    if recreate and client.collection_exists(name):
        client.delete_collection(name)
    if not client.collection_exists(name):
        # vectors_config={} → 벡터 비활성 collection (retrieve(id) 전용)
        client.create_collection(collection_name=name, vectors_config={})


def upsert_children(client, name: str, children: list[dict], *, batch_size: int) -> None:
    from qdrant_client.models import PointStruct

    for start in range(0, len(children), batch_size):
        batch = children[start : start + batch_size]
        points = [PointStruct(id=point_id(c["id"]), vector=c["vector"], payload=build_payload(c)) for c in batch]
        client.upsert(collection_name=name, points=points, wait=True)


def upsert_parents(client, name: str, parents: list[dict], *, batch_size: int) -> None:
    from qdrant_client.models import PointStruct

    for start in range(0, len(parents), batch_size):
        batch = parents[start : start + batch_size]
        points = [PointStruct(id=point_id(p["id"]), vector={}, payload=build_payload(p)) for p in batch]
        client.upsert(collection_name=name, points=points, wait=True)


# ─────────────────────────────────────────────────────────────────────────────
# 통계 (dry-run·실행 공통 — 태깅 분포·dedup·id 충돌 검증)
# ─────────────────────────────────────────────────────────────────────────────
def summarize(children: list[dict], parents: list[dict], removed: int) -> None:
    age = Counter(age_group_for(c["payload"]) for c in children)
    print(f"  child: {len(children):,}개 (dedup 제거 {removed:,}) | age_group {dict(age)}")
    print(f"  parent: {len(parents):,}개")
    # point id 충돌 검증 (int 변환 후 유일성)
    child_ids = [point_id(c["id"]) for c in children]
    parent_ids = [point_id(p["id"]) for p in parents]
    assert len(child_ids) == len(set(child_ids)), "child point_id 충돌 (dedup 후 중복 id)"
    assert len(parent_ids) == len(set(parent_ids)), "parent point_id 충돌"
    print(f"  point_id 유일성 OK (child {len(set(child_ids)):,} / parent {len(set(parent_ids)):,})")
    # 무결성: 남은 child 의 parent_id 가 parent 에 존재하는지 (dedup 후에도)
    parent_id_set = {p["id"] for p in parents}
    orphans = [c for c in children if c["payload"]["parent_id"] not in parent_id_set]
    if orphans:
        print(f"  ⚠ 고아 child {len(orphans)}개 (parent_id 미존재) — parent_chunks 재생성 필요")
    else:
        print("  parent_id 무결성 OK (고아 0)")


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="embedded child + parent → Qdrant 업로드")
    parser.add_argument(
        "--child-in", default=None, help="기본 chunks/embedded_child_chunks.jsonl (dry-run 시 child_chunks.jsonl 폴백)"
    )
    parser.add_argument("--parent-in", default=None, help="기본 chunks/parent_chunks.jsonl")
    parser.add_argument("--recreate", action="store_true", help="collection 삭제 후 재생성")
    parser.add_argument("--child-only", action="store_true")
    parser.add_argument("--parent-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="child 앞 N개만 (스모크)")
    parser.add_argument("--batch-size", type=int, default=cfg.UPLOAD_BATCH_SIZE)
    parser.add_argument("--prod", action="store_true", help="prod collection(medical_kb_prod, 3072d)")
    parser.add_argument("--dry-run", action="store_true", help="Qdrant 없이 태깅·dedup·id 통계만")
    parser.add_argument("--qdrant-url", default=None, help="기본 env QDRANT_URL 또는 localhost:6333")
    args = parser.parse_args()

    child_coll = cfg.COLLECTION_CHILD_PROD if args.prod else cfg.COLLECTION_CHILD_DEV
    dim = cfg.EMBEDDING_DIM_PROD if args.prod else cfg.EMBEDDING_DIM_DEV
    parent_coll = cfg.COLLECTION_PARENT

    # 입력 경로 — 실제 업로드는 임베딩(vector) 필수, dry-run 은 child_chunks.jsonl 폴백 허용
    embedded = cfg.CHUNKS_DIR / "embedded_child_chunks.jsonl"
    raw_child = cfg.CHUNKS_DIR / "child_chunks.jsonl"
    if args.child_in:
        child_path = Path(args.child_in)
    elif embedded.exists():
        child_path = embedded
    elif args.dry_run:
        child_path = raw_child  # 벡터 없이 로직만 검증
    else:
        raise SystemExit(f"입력 없음: {embedded}\n  먼저 embedder.py 로 임베딩하세요. (구조만 보려면 --dry-run)")
    parent_path = Path(args.parent_in) if args.parent_in else cfg.CHUNKS_DIR / "parent_chunks.jsonl"

    children = read_jsonl(child_path)
    parents = read_jsonl(parent_path)
    if args.limit:
        children = children[: args.limit]

    has_vector = bool(children) and "vector" in children[0]
    print(
        f"입력: child={child_path.name}({len(children):,}, vector={'있음' if has_vector else '없음'}) "
        f"parent={parent_path.name}({len(parents):,})"
    )
    print(f"대상: {child_coll}({dim}d) + {parent_coll}" + ("  [dry-run]" if args.dry_run else ""))

    # P1-5 dedup
    children, removed = dedup_children(children)

    print("\n[후처리 통계]")
    summarize(children, parents, removed)

    if args.dry_run:
        print("\n--dry-run: Qdrant 미연결. 위 통계로 태깅·dedup·id 검증 완료.")
        return

    if not has_vector:
        raise SystemExit(
            "child 에 vector 가 없습니다 — embedder.py 를 먼저 실행해 embedded_child_chunks.jsonl 을 생성하세요."
        )

    client = make_client(args.qdrant_url)

    if not args.parent_only:
        print(f"\n[child 업로드] → {child_coll}")
        ensure_child_collection(client, child_coll, dim, recreate=args.recreate)
        upsert_children(client, child_coll, children, batch_size=args.batch_size)
        print(f"  {len(children):,}개 upsert 완료")

    if not args.child_only:
        print(f"\n[parent 업로드] → {parent_coll}")
        ensure_parent_collection(client, parent_coll, recreate=args.recreate)
        upsert_parents(client, parent_coll, parents, batch_size=args.batch_size)
        print(f"  {len(parents):,}개 upsert 완료")

    print("\n업로드 완료. Qdrant 대시보드에서 collection 확인: http://localhost:6333/dashboard")


if __name__ == "__main__":
    main()
