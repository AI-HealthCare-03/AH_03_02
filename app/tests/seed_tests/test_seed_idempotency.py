"""seed_challenges 멱등성 회귀 테스트.

과거 버그: lifespan 시드가 매 기동마다 UserChallenge·Challenge 를 전부 삭제 후
재생성 → 재시작/배포 때마다 사용자 챌린지 진행이 초기화되고 challenge ID 가 바뀜.
수정: challenges 가 1건이라도 있으면 시드를 건너뛴다(멱등).
"""

from tortoise.contrib.test import TestCase

from app.core.seed import seed_challenges
from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack


class TestSeedIdempotency(TestCase):
    async def test_seed_skips_when_challenges_exist(self):
        """이미 챌린지가 있으면 시드는 기존 레코드를 건드리지 않는다(삭제·재생성 금지)."""
        existing = await Challenge.create(
            name="기존 챌린지",
            category=ChallengeCategory.HYDRATION,
            description="이미 존재",
            duration_days=1,
            track=ChallengeTrack.WELLNESS,
            stage=1,
        )
        before_ids = set(await Challenge.all().values_list("id", flat=True))

        await seed_challenges()

        after_ids = set(await Challenge.all().values_list("id", flat=True))
        # 기존 ID 그대로 유지(파괴적 재적재 안 함) — UserChallenge FK 보존의 핵심
        assert before_ids == after_ids
        assert await Challenge.get_or_none(id=existing.id) is not None

    async def test_seed_inserts_when_empty(self):
        """빈 상태에서는 시드가 정상 삽입한다(첫 기동)."""
        assert await Challenge.all().count() == 0

        await seed_challenges()

        assert await Challenge.all().count() > 0
