"""부하 테스트용 사용자 시드. 50명 사용자 + 검진·챌린지·체크인 데이터를 일괄 생성.

이메일: load001@loadtest.example ~ load050@loadtest.example
비번:   LoadTest123!

각 사용자에게:
- 건강검진 1건 (G2, eGFR=70 — Track A 챌린지 추천)
- 챌린지 2건 참여 (수분 + 운동)
- 체크인 10회 (지난 10일)

용도: locustfile.py에서 미리 만들어둔 계정 풀로 로그인 → 대시보드/챌린지 GET 부하.
"""

import asyncio
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tortoise import Tortoise

from app.core.db.databases import TORTOISE_ORM
from app.core.utils.security import hash_password
from app.models.challenge import Challenge, UserChallenge, UserChallengeStatus
from app.models.gamification import PointReason, PointTransaction
from app.models.health_check import AppGroup, CkdStage, HealthCheck
from app.models.users import Gender, User

USER_COUNT = 50
EMAIL_FMT = "load{:03d}@loadtest.example"
PASSWORD = "LoadTest123!"


async def wipe_existing() -> None:
    await User.filter(email__startswith="load", email__endswith="@loadtest.example").delete()


async def seed_one(idx: int, challenges: list[Challenge]) -> None:
    email = EMAIL_FMT.format(idx)
    user = await User.create(
        email=email,
        hashed_password=hash_password(PASSWORD),
        name=f"부하테스트{idx:03d}",
        gender=Gender.MALE if idx % 2 == 0 else Gender.FEMALE,
        birthday=date(1990, 1, 1),
        phone_number=f"010{99000000 + idx:08d}",  # 데모 계정(010000000XX)과 겹치지 않는 부하테스트 전용 범위
        email_verified=True,  # 부하테스트 로그인 통과 (이메일 인증 정책 도입 후 필요)
    )
    today = date.today()
    await HealthCheck.create(
        user_id=user.id,
        checked_date=today - timedelta(days=30),
        systolic_bp=120,
        diastolic_bp=80,
        fasting_glucose=95.0,
        weight=70.0,
        height=170.0,
        bmi=24.2,
        creatinine_mg_dl=1.1,
        egfr_estimated=70.0,
        ckd_stage=CkdStage.G2,
        app_group=AppGroup.G2,
    )
    # 2개 챌린지 참여
    for ch in challenges[:2]:
        uc = await UserChallenge.create(
            user_id=user.id,
            challenge_id=ch.id,
            started_at=today - timedelta(days=10),
            status=UserChallengeStatus.ACTIVE,
            streak_count=10,
            total_checkins=10,
            last_checkin_date=today - timedelta(days=1),
        )
        # 체크인 10회 (포인트 트랜잭션으로 잔디 히트맵 데이터 생성)
        for d in range(10):
            await PointTransaction.create(
                user_id=user.id,
                reason=PointReason.CHECKIN,
                amount=20,
                created_at=datetime.combine(today - timedelta(days=10 - d), datetime.min.time()).replace(tzinfo=UTC),
                extra={"challenge_id": ch.id, "user_challenge_id": uc.id},
            )


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        await wipe_existing()
        # 부하 테스트는 로그인 후 대시보드·챌린지 GET 위주라 트랙 무관 — 아무 챌린지 2건이면 충분
        challenges = await Challenge.all().limit(2)
        if len(challenges) < 2:
            print(f"챌린지 데이터 부족 ({len(challenges)}/2). 먼저 챌린지 시드 필요.")
            return
        for i in range(1, USER_COUNT + 1):
            await seed_one(i, challenges)
        print(f"✓ 부하 테스트 사용자 {USER_COUNT}명 생성 완료.")
        print(f"  이메일: load001@loadtest.example ~ load{USER_COUNT:03d}@loadtest.example")
        print(f"  비번:   {PASSWORD}")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
