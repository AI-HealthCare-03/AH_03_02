"""
챌린지 시드 데이터 자동 삽입 — FastAPI lifespan에서 호출.

멱등 정책: challenges 테이블이 비어 있을 때만 1회 삽입한다.
과거엔 매 기동마다 UserChallenge·Challenge 를 전부 삭제 후 재생성해서
재시작/배포 때마다 모든 사용자의 챌린지 참여·스트릭·체크인이 사라지는
데이터 손실이 있었다. 시드 내용을 갱신해야 할 때는 challenges 테이블을
비우고(또는 별도 마이그레이션/관리 도구로) 재기동하는 의도적 재시드 절차를 쓴다.
"""

import json
from pathlib import Path

_DATA_FILE = Path(__file__).parent.parent.parent / "src" / "ckd" / "data" / "challenges_v05.json"


async def seed_challenges() -> None:
    from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack

    if not _DATA_FILE.exists():
        print("[seed] challenges_v05.json 없음 — 건너뜀")
        return

    # 멱등: 이미 시드돼 있으면(챌린지가 1건이라도 있으면) 재적재하지 않는다.
    # → 재시작 시 챌린지 ID 안정 + 사용자 UserChallenge 참여·스트릭 보존.
    if await Challenge.all().count() > 0:
        print("[seed] 챌린지가 이미 존재 — 시드 건너뜀(멱등)")
        return

    challenges = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    inserted = 0
    for item in challenges:
        await Challenge.create(
            name=item["name"],
            category=ChallengeCategory(item["category"]),
            description=item["description"],
            duration_days=item["duration_days"],
            track=ChallengeTrack(item["track"]),
            stage=item["stage"],
        )
        inserted += 1

    print(f"[seed] 챌린지 {inserted}건 삽입 완료")
