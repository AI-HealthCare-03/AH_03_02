"""
챌린지 시드 데이터 자동 삽입 — FastAPI lifespan에서 호출.
v05: 트랙 enum 변경(A/B → 5종) 으로 기존 레코드 호환 불가 → 재적재 정책 적용.
"""

import json
from pathlib import Path

_DATA_FILE = Path(__file__).parent.parent.parent / "src" / "ckd" / "data" / "challenges_v05.json"


async def seed_challenges() -> None:
    from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack, UserChallenge

    if not _DATA_FILE.exists():
        print("[seed] challenges_v05.json 없음 — 건너뜀")
        return

    # 개발 단계: 트랙/카테고리 enum 변경으로 기존 챌린지 레코드 호환 불가 → 재적재
    await UserChallenge.all().delete()  # FK 먼저 삭제
    await Challenge.all().delete()

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
