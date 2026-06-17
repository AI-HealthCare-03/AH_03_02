from datetime import date

from app.models.challenge import (
    Challenge,
    ChallengeTrack,
    DailyChecklistLog,
    UserChallenge,
    UserChallengeProfile,
    UserChallengeStatus,
)
from app.models.health_check import HealthCheck
from app.models.lifestyle_survey import LifestyleSurvey


class ChallengeRepository:
    async def list_by_track(self, track: ChallengeTrack) -> list[Challenge]:
        return await Challenge.filter(track=track, is_active=True)

    async def list_by_track_and_stage(self, track: ChallengeTrack, stage: int) -> list[Challenge]:
        """트랙 + 스테이지 조합으로 챌린지 목록 조회."""
        return await Challenge.filter(track=track, stage=stage, is_active=True)

    async def get_by_id(self, challenge_id: int) -> Challenge | None:
        return await Challenge.get_or_none(id=challenge_id, is_active=True)


class UserChallengeRepository:
    async def get_active(self, user_id: int, challenge_id: int) -> UserChallenge | None:
        return await UserChallenge.get_or_none(user_id=user_id, challenge_id=challenge_id)

    async def create(self, user_id: int, challenge_id: int, started_at: date) -> UserChallenge:
        return await UserChallenge.create(
            user_id=user_id,
            challenge_id=challenge_id,
            started_at=started_at,
        )

    async def list_by_user(
        self,
        user_id: int,
        status: UserChallengeStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[UserChallenge]]:
        qs = UserChallenge.filter(user_id=user_id)
        if status is not None:
            qs = qs.filter(status=status)
        total = await qs.count()
        items = await qs.order_by("-created_at").offset(offset).limit(limit)
        return total, items

    async def get_by_id(self, user_challenge_id: int, user_id: int) -> UserChallenge | None:
        return await UserChallenge.get_or_none(id=user_challenge_id, user_id=user_id)

    async def save(self, user_challenge: UserChallenge) -> None:
        await user_challenge.save()

    async def list_active_by_user(self, user_id: int) -> list[UserChallenge]:
        return await UserChallenge.filter(user_id=user_id, status=UserChallengeStatus.ACTIVE)

    async def list_active_and_completed_by_user(self, user_id: int) -> list[UserChallenge]:
        return await UserChallenge.filter(
            user_id=user_id,
            status__in=[UserChallengeStatus.ACTIVE, UserChallengeStatus.COMPLETED],
        )


class UserChallengeProfileRepository:
    """사용자 챌린지 프로필(트랙·스테이지) CRUD."""

    async def get_by_user(self, user_id: int) -> UserChallengeProfile | None:
        return await UserChallengeProfile.get_or_none(user_id=user_id)

    async def upsert(
        self,
        user_id: int,
        track: ChallengeTrack,
        stage: int,
        auto_assigned: bool,
    ) -> UserChallengeProfile:
        """없으면 생성, 있으면 갱신."""
        profile = await UserChallengeProfile.get_or_none(user_id=user_id)
        if profile is None:
            profile = await UserChallengeProfile.create(
                user_id=user_id,
                track=track,
                stage=stage,
                auto_assigned=auto_assigned,
            )
        else:
            profile.track = track
            profile.stage = stage
            profile.auto_assigned = auto_assigned
            await profile.save()
        return profile


class DailyChecklistLogRepository:
    """일별 필수 체크리스트 기록 CRUD."""

    async def list_by_date(self, user_id: int, log_date: date) -> list[DailyChecklistLog]:
        return await DailyChecklistLog.filter(user_id=user_id, log_date=log_date).all()

    async def get_item(self, user_id: int, log_date: date, item_key: str) -> DailyChecklistLog | None:
        return await DailyChecklistLog.get_or_none(user_id=user_id, log_date=log_date, item_key=item_key)

    async def upsert_toggle(self, user_id: int, log_date: date, item_key: str) -> DailyChecklistLog:
        """항목이 없으면 checked=True로 생성, 있으면 checked 토글."""
        log = await DailyChecklistLog.get_or_none(user_id=user_id, log_date=log_date, item_key=item_key)
        if log is None:
            log = await DailyChecklistLog.create(
                user_id=user_id,
                log_date=log_date,
                item_key=item_key,
                checked=True,
            )
        else:
            log.checked = not log.checked
            await log.save()
        return log


class HealthCheckSnapshotRepository:
    """챌린지 트랙 배정용 최신 검진 조회 (별도 리포지토리)."""

    async def get_latest(self, user_id: int) -> HealthCheck | None:
        return await HealthCheck.filter(user_id=user_id).order_by("-checked_date", "-id").first()


class LifestyleSurveySnapshotRepository:
    """챌린지 트랙 배정용 최신 문진 조회 (별도 리포지토리)."""

    async def get_latest(self, user_id: int) -> LifestyleSurvey | None:
        return await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()
