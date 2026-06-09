from datetime import date, timedelta

from fastapi import HTTPException
from starlette import status
from tortoise.transactions import in_transaction

from app.dtos.challenge import (
    AbandonChallengeResponse,
    CancelCheckinResponse,
    CategoryProgress,
    CategoryProgressResponse,
    ChallengeListResponse,
    ChallengeResponse,
    CheckinAwardResponse,
    CheckInResponse,
    EggUpdateResponse,
    EmotionDay,
    HeatmapDay,
    HeatmapResponse,
    JoinChallengeRequest,
    UserChallengeListResponse,
    UserChallengeResponse,
    WeeklyEmotionResponse,
)
from app.models.challenge import (
    Challenge,
    ChallengeCategory,
    ChallengeTrack,
    CheckinEmotion,
    CheckinEmotionLog,
    UserChallenge,
    UserChallengeStatus,
)
from app.models.health_check import AppGroup
from app.repositories.challenge_repository import ChallengeRepository, UserChallengeRepository
from app.services.charge_mode import ChargeModeService
from app.services.eggs import EggService
from app.services.notification import NotificationService
from app.services.points import PointService
from app.services.streak_protect import StreakProtectService

_GROUP_TO_TRACK: dict[AppGroup, ChallengeTrack] = {
    AppGroup.G1: ChallengeTrack.A,
    AppGroup.G2: ChallengeTrack.A,
    AppGroup.G3: ChallengeTrack.B,
    AppGroup.G4: ChallengeTrack.B,
}


class ChallengeService:
    def __init__(self) -> None:
        self._repo = ChallengeRepository()
        self._user_repo = UserChallengeRepository()
        self._notif = NotificationService()
        self._points = PointService()
        self._eggs = EggService()
        self._charge = ChargeModeService()

    async def list_challenges(self, app_group: AppGroup | None) -> ChallengeListResponse:
        """사용자 App 그룹에 맞는 챌린지 목록 반환. 그룹 미입력 시 빈 목록."""
        if app_group is None:
            return ChallengeListResponse(total=0, items=[])

        track = _GROUP_TO_TRACK[app_group]
        items = await self._repo.list_by_track(track)
        return ChallengeListResponse(
            total=len(items),
            items=[ChallengeResponse.model_validate(c) for c in items],
        )

    async def join_challenge(self, user_id: int, dto: JoinChallengeRequest) -> UserChallengeResponse:
        challenge = await self._repo.get_by_id(dto.challenge_id)
        if challenge is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="챌린지를 찾을 수 없습니다.")

        existing = await self._user_repo.get_active(user_id, dto.challenge_id)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 참여 중인 챌린지입니다.")

        uc = await self._user_repo.create(
            user_id=user_id,
            challenge_id=dto.challenge_id,
            started_at=dto.started_at,
        )
        await self._notif.notify_challenge_joined(user_id, challenge.name, uc.id)
        return UserChallengeResponse.model_validate(uc)

    async def list_my_challenges(
        self,
        user_id: int,
        status_filter: UserChallengeStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> UserChallengeListResponse:
        total, items = await self._user_repo.list_by_user(user_id, status_filter, limit, offset)
        return UserChallengeListResponse(
            total=total,
            items=[UserChallengeResponse.model_validate(uc) for uc in items],
        )

    async def checkin(
        self, user_challenge_id: int, user_id: int, today: date, emotion: CheckinEmotion | None = None
    ) -> CheckInResponse:
        # 체크인 처리 전에 어제 보호권 자동 소모 평가 (streak 계산에 영향)
        await StreakProtectService().evaluate(user_id, today)

        uc = await self._user_repo.get_by_id(user_challenge_id, user_id)
        if uc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="참여 중인 챌린지를 찾을 수 없습니다.")

        if uc.status != UserChallengeStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="완료되거나 포기한 챌린지에는 체크인할 수 없습니다.",
            )

        if uc.last_checkin_date == today:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="오늘은 이미 체크인했습니다.")

        # 스트릭 계산: 어제 체크인 → 연속, 아니면 1로 리셋
        if uc.last_checkin_date == today - timedelta(days=1):
            uc.streak_count += 1
        else:
            uc.streak_count = 1

        uc.total_checkins += 1
        uc.last_checkin_date = today
        if emotion is not None:
            uc.last_emotion = emotion
            # 일별 감정 로그 (같은 날 여러 챌린지 체크인하면 마지막 감정으로 덮어쓰기)
            existing_log = await CheckinEmotionLog.filter(user_id=user_id, log_date=today).first()
            if existing_log:
                existing_log.emotion = emotion
                await existing_log.save()
            else:
                await CheckinEmotionLog.create(user_id=user_id, log_date=today, emotion=emotion)

        # 챌린지 완료 체크 (fetch challenge duration_days)
        challenge = await uc.challenge
        if uc.total_checkins >= challenge.duration_days:
            uc.status = UserChallengeStatus.COMPLETED
            message = f"챌린지를 완료했습니다! 총 {uc.total_checkins}일 달성."
        else:
            remaining = challenge.duration_days - uc.total_checkins
            message = f"체크인 완료! 연속 {uc.streak_count}일째입니다. 목표까지 {remaining}일 남았습니다."

        await self._user_repo.save(uc)

        # 포인트 적립 (체크인 기본 +20 + 럭키 10% + 스트릭 마일스톤 + 풀 참여)
        award = await self._points.award_checkin(
            user_id=user_id, challenge_id=challenge.id, streak_count=uc.streak_count, today=today
        )

        # 알 진행률 +1 + 단계 보너스 + 알림 + 부화 처리
        egg_update = await self._eggs.progress_and_check(user_id=user_id, challenge_id=challenge.id)

        # 충전 모드 평가 (체크인 했으니 active였다면 탈출)
        await self._charge.evaluate(user_id=user_id, today=today)

        if uc.status == UserChallengeStatus.COMPLETED:
            await self._notif.notify_challenge_completed(user_id, challenge.name, uc.total_checkins, uc.id)
        else:
            await self._notif.notify_checkin_done(user_id, challenge.name, uc.streak_count, uc.id)

        return CheckInResponse(
            id=uc.id,
            streak_count=uc.streak_count,
            total_checkins=uc.total_checkins,
            last_checkin_date=uc.last_checkin_date,
            status=uc.status,
            message=message,
            award=CheckinAwardResponse(
                base=award.base,
                lucky=award.lucky,
                lucky_extra=award.lucky_extra,
                streak_bonus=award.streak_bonus,
                streak_milestone=award.streak_milestone,
                full_participation=award.full_participation,
                full_participation_bonus=award.full_participation_bonus,
                total=award.total,
            ),
            egg=EggUpdateResponse(
                progress_checkins=egg_update.progress_checkins,
                current_stage=egg_update.current_stage,
                goal_70_just_alerted=egg_update.goal_70_just_alerted,
                goal_90_just_alerted=egg_update.goal_90_just_alerted,
                stage_bonus=egg_update.stage_bonus,
                stage_milestone=egg_update.stage_milestone,
                hatched=egg_update.hatched,
                evolved_to=egg_update.evolved_to,
                is_legendary=egg_update.is_legendary,
                species=egg_update.species.value if egg_update.species else None,
                character_name=egg_update.character_name,
                new_egg_no=egg_update.new_egg_no,
            ),
        )

    async def get_heatmap(self, user_id: int, weeks: int = 26) -> HeatmapResponse:
        """챌린지 잔디 히트맵용 일별 체크인 카운트.

        PointTransaction.reason=CHECKIN/LUCKY 기준으로 일별 카운트 집계.
        주 시작은 월요일.
        """
        from datetime import timedelta

        from app.models.gamification import PointReason, PointTransaction

        today = date.today()
        # 26주(=182일) 전부터, 단 주 단위 정렬을 위해 월요일로 맞춤
        weeks_ago_monday = today - timedelta(days=today.weekday() + (weeks - 1) * 7)
        end_date = today
        # 시작일 자정 이후의 체크인만
        from datetime import datetime, time

        start_dt = datetime.combine(weeks_ago_monday, time.min)
        rows = await PointTransaction.filter(
            user_id=user_id,
            reason__in=[PointReason.CHECKIN, PointReason.LUCKY],
            created_at__gte=start_dt,
        ).values("created_at")

        # 일별 카운트
        counts: dict[date, int] = {}
        for row in rows:
            d = row["created_at"].date()
            counts[d] = counts.get(d, 0) + 1

        # 시작일부터 오늘까지 모든 날짜 채우기
        days = []
        max_count = 0
        cur = weeks_ago_monday
        while cur <= end_date:
            c = counts.get(cur, 0)
            days.append(HeatmapDay(date=cur, count=c))
            if c > max_count:
                max_count = c
            cur += timedelta(days=1)

        return HeatmapResponse(weeks=weeks, today=today, days=days, max_count=max_count)

    async def get_category_progress(self, user_id: int) -> CategoryProgressResponse:
        """카테고리 5종별 active 챌린지 평균 진행률 (REQ-DASH-001 ⑥)."""
        active_list = await self._user_repo.list_active_by_user(user_id)
        # 카테고리별 집계
        by_cat: dict[ChallengeCategory, dict] = {
            cat: {"active_count": 0, "total_checkins": 0, "total_duration": 0} for cat in ChallengeCategory
        }
        for uc in active_list:
            ch = await uc.challenge
            cat = ch.category
            by_cat[cat]["active_count"] += 1
            by_cat[cat]["total_checkins"] += uc.total_checkins
            by_cat[cat]["total_duration"] += ch.duration_days

        items = []
        # 명세 순서: HYDRATION/EXERCISE/DIET/SLEEP/STRESS
        for cat in [
            ChallengeCategory.HYDRATION,
            ChallengeCategory.EXERCISE,
            ChallengeCategory.DIET,
            ChallengeCategory.SLEEP,
            ChallengeCategory.STRESS,
        ]:
            data = by_cat[cat]
            percent = 0
            if data["total_duration"] > 0:
                percent = int(min(100, round(data["total_checkins"] / data["total_duration"] * 100)))
            items.append(
                CategoryProgress(
                    category=cat,
                    percent=percent,
                    active_count=data["active_count"],
                    total_checkins=data["total_checkins"],
                    total_duration=data["total_duration"],
                )
            )
        return CategoryProgressResponse(items=items)

    async def get_weekly_emotion(self, user_id: int) -> WeeklyEmotionResponse:
        """최근 7일 감정 기록 (REQ-DASH-001 ⑤ 감정 듀얼 축)."""
        from datetime import timedelta

        today = date.today()
        start = today - timedelta(days=6)
        logs = await CheckinEmotionLog.filter(user_id=user_id, log_date__gte=start).all()
        by_date = {log.log_date: log.emotion for log in logs}

        days = []
        cur = start
        while cur <= today:
            days.append(EmotionDay(date=cur, emotion=by_date.get(cur)))
            cur += timedelta(days=1)
        return WeeklyEmotionResponse(days=days)

    async def _rollback_today_checkin(self, uc: UserChallenge, challenge: Challenge, today: date) -> int:
        """오늘 체크인 1건 롤백: 당일 지급 포인트 회수 + 카운트(total·streak·last_date) 롤백.

        cancel_checkin·abandon이 공유한다. 호출 측의 in_transaction 안에서 실행하며,
        status 변경(ACTIVE 복귀 / ABANDONED)은 호출 측 책임. 반환값=회수된 포인트(양수, 0이면 없음).

        last_checkin_date는 날짜별 체크인 로그가 없어 근사값 — streak이 남으면 어제, 없으면 None.
        """
        points_revoked = await self._points.revoke_checkin(user_id=uc.user_id, challenge_id=challenge.id, today=today)
        uc.total_checkins = max(0, uc.total_checkins - 1)
        uc.streak_count = max(0, uc.streak_count - 1)
        uc.last_checkin_date = today - timedelta(days=1) if uc.streak_count > 0 else None
        return points_revoked

    async def cancel_checkin(self, user_id: int, user_challenge_id: int, today: date) -> CancelCheckinResponse:
        """오늘 체크인을 완전 롤백.

        - last_checkin_date != today 이면 400 (오늘 체크인 내역 없음)
        - total_checkins -= 1, streak_count = max(0, streak_count-1)
        - last_checkin_date: 별도 날짜 로그 없음 → streak>0이면 today-1, 아니면 None
        - 체크인 포인트 역적립 (CHECKIN/LUCKY/STREAK_BONUS/FULL_PARTICIPATION)
        - COMPLETED → ACTIVE 복귀
        - in_transaction으로 원자성 보장
        """
        uc = await self._user_repo.get_by_id(user_challenge_id, user_id)
        if uc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="참여 중인 챌린지를 찾을 수 없습니다.")

        if uc.last_checkin_date != today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="오늘 체크인하지 않았습니다.",
            )

        challenge = await uc.challenge

        async with in_transaction():
            points_revoked = await self._rollback_today_checkin(uc, challenge, today)

            # COMPLETED였으면 ACTIVE로 복귀
            if uc.status == UserChallengeStatus.COMPLETED:
                uc.status = UserChallengeStatus.ACTIVE

            await self._user_repo.save(uc)

        return CancelCheckinResponse(
            id=uc.id,
            streak_count=uc.streak_count,
            total_checkins=uc.total_checkins,
            last_checkin_date=uc.last_checkin_date,
            status=uc.status,
            points_revoked=points_revoked,
            message="오늘 체크인이 취소되었습니다.",
        )

    async def abandon(self, user_id: int, user_challenge_id: int, today: date) -> AbandonChallengeResponse:
        """챌린지 참여 해제 (ABANDONED).

        - 레코드 삭제 아님 — 이력 유지 (과거 정당한 체크인 보상은 보존)
        - 오늘 체크인이 있으면 '당일 지급분만' 회수 + 카운트 롤백 (cancel_checkin과 동일 범위)
        - 이미 ABANDONED이면 409
        - in_transaction으로 원자성 보장
        """
        uc = await self._user_repo.get_by_id(user_challenge_id, user_id)
        if uc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="참여 중인 챌린지를 찾을 수 없습니다.")

        if uc.status == UserChallengeStatus.ABANDONED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 포기한 챌린지입니다.",
            )

        points_revoked = 0
        async with in_transaction():
            # 오늘 체크인했다면 당일 지급분만 회수 + 카운트 롤백 (과거분은 보존)
            if uc.last_checkin_date == today:
                challenge = await uc.challenge
                points_revoked = await self._rollback_today_checkin(uc, challenge, today)

            uc.status = UserChallengeStatus.ABANDONED
            await self._user_repo.save(uc)

        return AbandonChallengeResponse(
            id=uc.id,
            status=uc.status,
            points_revoked=points_revoked,
            message="챌린지 참여를 해제했습니다.",
        )
