from datetime import date, timedelta

from fastapi import HTTPException
from starlette import status
from tortoise.transactions import in_transaction

from app.dtos.challenge import (
    AbandonChallengeResponse,
    CalendarDay,
    CancelCheckinResponse,
    CategoryProgress,
    CategoryProgressResponse,
    ChallengeListResponse,
    ChallengeResponse,
    CheckinAwardResponse,
    CheckInResponse,
    ChecklistToggleResponse,
    DailyChecklistItemResponse,
    DailyChecklistResponse,
    EggUpdateResponse,
    EmotionDay,
    HeatmapDay,
    HeatmapResponse,
    JoinChallengeRequest,
    MonthlyCalendarResponse,
    MyTrackResponse,
    TrackCategoryInfo,
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
from app.models.users import User
from app.repositories.challenge_repository import (
    ChallengeRepository,
    DailyChecklistLogRepository,
    HealthCheckSnapshotRepository,
    LifestyleSurveySnapshotRepository,
    UserChallengeProfileRepository,
    UserChallengeRepository,
)
from app.services.challenge_reference import (
    CATEGORY_LABEL,
    REQUIRED_CHECKLIST,
    STAGE_LABEL,
    TRACK_CATEGORIES,
    TRACK_LABEL,
    assign_track,
)
from app.services.charge_mode import ChargeModeService
from app.services.eggs import EggService
from app.services.notification import NotificationService
from app.services.points import PointService
from app.services.streak_protect import StreakProtectService

# AppGroup(G1~G4 StrEnum) → assign_track 입력 문자열(A/B/C/D) 변환 테이블.
# 근거: app/services/health_check.py:622 주석 및 M1_GROUP_TITLE 키 규약.
_APP_GROUP_TO_LETTER: dict[str, str] = {
    "G1": "A",  # 신장 집중 관리군 (eGFR < 60)
    "G2": "B",  # 신장 위험 관리군 (eGFR >= 60 + 임상 마커)
    "G3": "C",  # 신장 사전 관리군 (모델 위험신호)
    "G4": "D",  # 건강 습관 형성군 (정상)
    "CKD": "CKD",  # CKD 진단 + 비투석(보존기)
    "DIALYSIS": "DIALYSIS",  # CKD 진단 + 투석/이식
}


def _app_group_to_letter(app_group_value: str | None) -> str | None:
    """AppGroup StrEnum 값(G1~G4)을 assign_track 입력(A~D)으로 변환."""
    if app_group_value is None:
        return None
    return _APP_GROUP_TO_LETTER.get(app_group_value)


def _build_my_track_response(profile) -> MyTrackResponse:
    """UserChallengeProfile 객체 → MyTrackResponse DTO 변환 헬퍼."""
    track_key = profile.track.value if hasattr(profile.track, "value") else str(profile.track)
    categories = [
        TrackCategoryInfo(
            category=cat,
            label=CATEGORY_LABEL.get(cat, cat),
        )
        for cat in TRACK_CATEGORIES.get(track_key, [])
    ]
    return MyTrackResponse(
        track=profile.track,
        track_label=TRACK_LABEL.get(track_key, track_key),
        stage=profile.stage,
        stage_label=STAGE_LABEL.get(profile.stage, str(profile.stage)),
        auto_assigned=profile.auto_assigned,
        categories=categories,
    )


class ChallengeService:
    def __init__(self) -> None:
        self._repo = ChallengeRepository()
        self._user_repo = UserChallengeRepository()
        self._profile_repo = UserChallengeProfileRepository()
        self._checklist_repo = DailyChecklistLogRepository()
        self._hc_repo = HealthCheckSnapshotRepository()
        self._survey_repo = LifestyleSurveySnapshotRepository()
        self._notif = NotificationService()
        self._points = PointService()
        self._eggs = EggService()
        self._charge = ChargeModeService()

    # ── 트랙 자동배정 · 조회 ──────────────────────────────────────────────────

    async def _compute_track(self, user_id: int) -> ChallengeTrack:
        """최신 검진·문진 기준 트랙 자동배정 (PDF 명세: 항상 자동, 사용자 변경 불가).

        트랙 결정 입력은 app_group(A~D)·ckd_diagnosed·dialysis_type.
        """
        hc = await self._hc_repo.get_latest(user_id)
        survey = await self._survey_repo.get_latest(user_id)

        app_group_letter = _app_group_to_letter(hc.app_group.value if hc and hc.app_group else None)
        ckd_diagnosed: bool = bool(survey.ckd_diagnosed) if survey else False
        # dialysis_type은 문진(survey) 단일 진실에서 직접 참조 — 검진 없이도 DIALYSIS 판정 가능
        dialysis_type: str | None = survey.dialysis_type.value if survey and survey.dialysis_type else None

        return assign_track(
            app_group=app_group_letter,
            ckd_diagnosed=ckd_diagnosed,
            dialysis_type=dialysis_type,
        )

    async def get_my_track(self, user_id: int) -> MyTrackResponse:
        """사용자 트랙 조회 — 항상 최신 검진·문진으로 자동 재배정 (PDF 명세).

        트랙은 사용자가 변경할 수 없고, 검진/진단 변화 시 동일 로직으로 재스크리닝된다.
        stage(배지 단계)는 사용자 설정값으로 유지한다.
        - 프로필 없음 → 자동배정 결과로 신규 생성
        - 프로필 있음 + 트랙 불일치 → 재배정 결과로 갱신 (stage 유지)
        """
        computed_track = await self._compute_track(user_id)

        profile = await self._profile_repo.get_by_user(user_id)
        if profile is None:
            profile = await self._profile_repo.upsert(
                user_id=user_id,
                track=computed_track,
                stage=1,
                auto_assigned=True,
            )
        elif profile.track != computed_track:
            # 검진/진단 변화 → 트랙 재배정 (stage는 사용자 값 유지)
            profile = await self._profile_repo.upsert(
                user_id=user_id,
                track=computed_track,
                stage=profile.stage,
                auto_assigned=True,
            )

        # 챌린지 스테이지 → 캐릭터 창 배경(proficiency) 동기화 (기존 유저 백필 포함)
        await self._sync_proficiency(user_id, profile.stage)
        return _build_my_track_response(profile)

    async def update_my_track(self, user_id: int, stage: int) -> MyTrackResponse:
        """배지 단계(stage)만 변경. 트랙은 PDF 명세상 사용자 변경 불가 — 자동배정 유지.

        과거 stage 변경이 트랙을 수동 고정(auto_assigned=False)시켜 그룹↔트랙 연동이
        끊겼던 버그를 막기 위해, 여기서도 트랙은 항상 재계산 결과로 저장한다.
        """
        computed_track = await self._compute_track(user_id)
        profile = await self._profile_repo.upsert(
            user_id=user_id,
            track=computed_track,
            stage=stage,
            auto_assigned=True,
        )
        # 챌린지 스테이지 → 캐릭터 창 배경(proficiency) 동기화
        await self._sync_proficiency(user_id, stage)
        return _build_my_track_response(profile)

    @staticmethod
    async def _sync_proficiency(user_id: int, stage: int) -> None:
        """챌린지 스테이지(1~4)를 user.proficiency에 동기화 — 캐릭터 창 배경(BackgroundImage) 결정용.

        proficiency 갱신 로직이 원래 없어 모든 유저가 1(잔디)에 고정됐던 문제를 해결한다.
        스테이지는 1~4 범위로 클램프한다.
        """
        await User.filter(id=user_id).update(proficiency=max(1, min(stage, 4)))

    # ── 챌린지 목록 (트랙·스테이지 기반) ─────────────────────────────────────

    async def list_challenges(
        self,
        track: ChallengeTrack | None = None,
        stage: int | None = None,
    ) -> ChallengeListResponse:
        """트랙·스테이지에 맞는 챌린지 목록 반환.

        track 미지정 시 빈 목록.
        stage 지정 시 해당 스테이지만, 미지정 시 트랙 전체.
        """
        if track is None:
            return ChallengeListResponse(total=0, items=[])

        if stage is not None:
            items = await self._repo.list_by_track_and_stage(track, stage)
        else:
            items = await self._repo.list_by_track(track)

        return ChallengeListResponse(
            total=len(items),
            items=[ChallengeResponse.model_validate(c) for c in items],
        )

    # ── 필수 체크리스트 ───────────────────────────────────────────────────────

    async def get_daily_checklist(self, user_id: int, today: date) -> DailyChecklistResponse:
        """오늘의 필수 체크리스트 조회.

        사용자 프로필 트랙의 REQUIRED_CHECKLIST(4항목) + 오늘 DailyChecklistLog 상태 반영.
        프로필이 없으면 WELLNESS 기본 트랙으로 처리.
        """
        profile = await self._profile_repo.get_by_user(user_id)
        if profile is None:
            track = ChallengeTrack.WELLNESS
        else:
            track = profile.track

        track_key = track.value if hasattr(track, "value") else str(track)
        checklist_items = REQUIRED_CHECKLIST.get(track_key, [])

        # 오늘 이미 체크된 항목 조회
        logs = await self._checklist_repo.list_by_date(user_id, today)
        checked_map: dict[str, bool] = {log.item_key: log.checked for log in logs}

        items = [
            DailyChecklistItemResponse(
                item_key=item_key,
                text=text,
                checked=checked_map.get(item_key, False),
            )
            for item_key, text in checklist_items
        ]

        return DailyChecklistResponse(date=today, track=track, items=items)

    async def toggle_daily_checklist(self, user_id: int, item_key: str, today: date) -> ChecklistToggleResponse:
        """필수 체크리스트 항목 토글 + 포인트·알 성장 연동.

        - 항목 체크(on): +5 적립 / 해제(off): -5 회수 (당일 순합 멱등)
        - 4개 전체완료로 전이: +30 보너스 + 알 진행도 +1 (EggService, 체크인과 동일 경로)
        - 전체완료 깨짐: -30 회수 + 알 진행도 -1 롤백 (선택 챌린지 취소와 동일 정책)
        - in_transaction 원자성
        """
        profile = await self._profile_repo.get_by_user(user_id)
        track = profile.track if profile else ChallengeTrack.WELLNESS
        track_key = track.value if hasattr(track, "value") else str(track)
        checklist_items = REQUIRED_CHECKLIST.get(track_key, [])
        valid_keys = {k for k, _ in checklist_items}

        if item_key not in valid_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"유효하지 않은 체크리스트 항목입니다: {item_key}",
            )

        required_count = len(checklist_items)
        text = next((t for k, t in checklist_items if k == item_key), item_key)

        egg_update = None
        full_bonus = 0
        async with in_transaction():
            log = await self._checklist_repo.upsert_toggle(user_id, today, item_key)
            item_delta = await self._points.toggle_checklist_item_points(user_id, item_key, today, checked=log.checked)

            logs = await self._checklist_repo.list_by_date(user_id, today)
            checked_count = sum(1 for lg in logs if lg.checked)
            now_complete = required_count > 0 and checked_count == required_count

            if log.checked and now_complete:
                full_bonus = await self._points.award_checklist_full(user_id, today)
                if full_bonus > 0:
                    egg_update = await self._eggs.progress_and_check(user_id=user_id)
            # 전체완료가 깨질 때만 -30 회수. 부분 미체크(원래 미완료)에서도 이 분기에 들어오나,
            # revoke_checklist_full 은 멱등 — 회수할 CHECKLIST_FULL 보너스가 없으면 0을 반환하므로 안전.
            elif not log.checked and not now_complete:
                revoked = await self._points.revoke_checklist_full(user_id, today)
                full_bonus = -revoked
                if revoked > 0:
                    await self._eggs.rollback_checkin(user_id)

        egg_dto = None
        if egg_update is not None:
            egg_dto = EggUpdateResponse(
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
            )

        return ChecklistToggleResponse(
            item_key=log.item_key,
            text=text,
            checked=log.checked,
            points_awarded=item_delta + full_bonus,
            all_completed=now_complete,
            full_bonus_awarded=full_bonus if full_bonus > 0 else 0,
            egg=egg_dto,
        )

    # ── 챌린지 참여 ──────────────────────────────────────────────────────────

    async def join_challenge(self, user_id: int, dto: JoinChallengeRequest) -> UserChallengeResponse:
        challenge = await self._repo.get_by_id(dto.challenge_id)
        if challenge is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="챌린지를 찾을 수 없습니다.")

        existing = await self._user_repo.get_active(user_id, dto.challenge_id)
        if existing is not None:
            # 해제(ABANDONED)했던 챌린지를 다시 선택 → 재활성화(ACTIVE 복귀, 이력 유지).
            # 같은 (user, challenge)에 행이 하나라 새로 create하면 unique 충돌 → 기존 행 재사용.
            if existing.status == UserChallengeStatus.ABANDONED:
                existing.status = UserChallengeStatus.ACTIVE
                existing.started_at = dto.started_at
                await self._user_repo.save(existing)
                await self._notif.notify_challenge_joined(user_id, challenge.name, existing.id)
                return UserChallengeResponse.model_validate(existing)
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

    # ── 체크인 ───────────────────────────────────────────────────────────────

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

    # ── 히트맵 ───────────────────────────────────────────────────────────────

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
        # 취소(CHECKIN_CANCEL)도 함께 조회해 일별로 차감 → 대시보드 '총 체크인'(UserChallenge 롤백)과 정합.
        rows = await PointTransaction.filter(
            user_id=user_id,
            reason__in=[PointReason.CHECKIN, PointReason.LUCKY, PointReason.CHECKIN_CANCEL],
            created_at__gte=start_dt,
        ).values("created_at", "reason")

        # 일별 카운트 (취소는 -1)
        counts: dict[date, int] = {}
        for row in rows:
            d = row["created_at"].date()
            delta = -1 if row["reason"] == PointReason.CHECKIN_CANCEL else 1
            counts[d] = counts.get(d, 0) + delta

        # 시작일부터 오늘까지 모든 날짜 채우기
        days = []
        max_count = 0
        cur = weeks_ago_monday
        while cur <= end_date:
            c = max(counts.get(cur, 0), 0)  # 취소가 교차일로 넘어가도 음수 방지
            days.append(HeatmapDay(date=cur, count=c))
            if c > max_count:
                max_count = c
            cur += timedelta(days=1)

        return HeatmapResponse(weeks=weeks, today=today, days=days, max_count=max_count)

    @staticmethod
    async def _calendar_checked_by_date(user_id: int, start: date, end: date) -> dict[date, set]:
        """월 범위 내 checked=True 필수항목을 날짜→item_key set으로 집계."""
        from app.models.challenge import DailyChecklistLog

        logs = await DailyChecklistLog.filter(
            user_id=user_id, log_date__gte=start, log_date__lte=end, checked=True
        ).values("log_date", "item_key")
        result: dict[date, set] = {}
        for lg in logs:
            result.setdefault(lg["log_date"], set()).add(lg["item_key"])
        return result

    @staticmethod
    async def _calendar_selected_by_date(user_id: int, start: date, end: date) -> dict[date, set]:
        """월 범위 내 선택 체크인 net>0 카테고리를 날짜→category set으로 집계."""
        from datetime import datetime, time

        from app.models.challenge import Challenge
        from app.models.gamification import PointReason, PointTransaction

        start_dt = datetime.combine(start, time.min)
        end_exclusive = datetime.combine(end + timedelta(days=1), time.min)
        rows = await PointTransaction.filter(
            user_id=user_id,
            reason__in=[PointReason.CHECKIN, PointReason.LUCKY, PointReason.CHECKIN_CANCEL],
            created_at__gte=start_dt,
            created_at__lt=end_exclusive,
        ).values("created_at", "reason", "extra")
        cids = {
            r["extra"].get("challenge_id")
            for r in rows
            if isinstance(r["extra"], dict) and r["extra"].get("challenge_id")
        }
        cat_by_cid: dict[int, str] = {}
        if cids:
            chs = await Challenge.filter(id__in=list(cids)).values("id", "category")
            cat_by_cid = {c["id"]: c["category"] for c in chs}
        net: dict[tuple, int] = {}
        for r in rows:
            extra = r["extra"] if isinstance(r["extra"], dict) else {}
            cat = cat_by_cid.get(extra.get("challenge_id"))
            if not cat:
                continue
            d = r["created_at"].date()
            delta = -1 if r["reason"] == PointReason.CHECKIN_CANCEL else 1
            net[(d, cat)] = net.get((d, cat), 0) + delta
        result: dict[date, set] = {}
        for (d, cat), v in net.items():
            if v > 0:
                result.setdefault(d, set()).add(cat)
        return result

    async def get_monthly_calendar(self, user_id: int, year_month: str | None = None) -> MonthlyCalendarResponse:
        """월별 달성 달력 — 날짜별 required(필수 체크 전부)·selected_count(카테고리별 체크인)·level.

        기존 로그(DailyChecklistLog + PointTransaction) 월 범위 1회 조회 후 메모리 집계. 마스코트 불변.
        """
        today = date.today()
        if year_month:
            y, m = (int(p) for p in year_month.split("-"))
        else:
            y, m = today.year, today.month
        start = date(y, m, 1)
        end = (date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)) - timedelta(days=1)

        profile = await self._profile_repo.get_by_user(user_id)
        track = profile.track if profile else ChallengeTrack.WELLNESS
        track_key = track.value if hasattr(track, "value") else str(track)
        required_count = len(REQUIRED_CHECKLIST.get(track_key, []))
        required_keys = {k for k, _ in REQUIRED_CHECKLIST.get(track_key, [])}

        checked_by_date = await self._calendar_checked_by_date(user_id, start, end)
        selected_by_date = await self._calendar_selected_by_date(user_id, start, end)

        days: list[CalendarDay] = []
        achieved = gold = streak = max_streak = 0
        cur = start
        while cur <= end:
            req = required_count > 0 and len(checked_by_date.get(cur, set()) & required_keys) >= required_count
            sel_count = len(selected_by_date.get(cur, set()))
            if not req:
                level = "none"
            elif sel_count == 0:
                level = "basic"
            elif sel_count <= 2:
                level = "silver"
            else:
                level = "gold"
            days.append(CalendarDay(date=cur, required=req, selected_count=sel_count, level=level))
            if level != "none":
                achieved += 1
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
            if level == "gold":
                gold += 1
            cur += timedelta(days=1)

        return MonthlyCalendarResponse(
            year_month=f"{y:04d}-{m:02d}",
            days=days,
            achieved_days=achieved,
            gold_days=gold,
            max_streak=max_streak,
        )

    # ── 카테고리 진행률 ───────────────────────────────────────────────────────

    async def get_category_progress(self, user_id: int) -> CategoryProgressResponse:
        """카테고리 5종별 이번 주 실천 일수 기반 완료율 (REQ-DASH-001 ⑥).

        percent = 이번 주 체크인한 unique 날짜 수 / 7 * 100 (매주 월요일 자동 리셋).
        - last_checkin_date의 고유 날짜를 카테고리별로 집계
        - ACTIVE + 이번 주 체크인, COMPLETED + 이번 주 마지막 체크인 포함
        - ABANDONED / 이번 주 체크인 없는 과거 COMPLETED: 제외
        """
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # 이번 주 월요일
        days_in_week = 7

        uc_list = await self._user_repo.list_active_and_completed_by_user(user_id)

        by_cat: dict[ChallengeCategory, dict] = {
            cat: {"active_count": 0, "checked_dates": set()} for cat in ChallengeCategory
        }
        for uc in uc_list:
            ch = await uc.challenge
            cat = ch.category
            is_valid = uc.status in (UserChallengeStatus.ACTIVE, UserChallengeStatus.COMPLETED)
            if not is_valid:
                continue
            by_cat[cat]["active_count"] += 1
            if uc.last_checkin_date and uc.last_checkin_date >= week_start:
                by_cat[cat]["checked_dates"].add(uc.last_checkin_date)

        items = []
        for cat in [
            ChallengeCategory.HYDRATION,
            ChallengeCategory.EXERCISE,
            ChallengeCategory.DIET,
            ChallengeCategory.SLEEP,
            ChallengeCategory.STRESS,
        ]:
            data = by_cat[cat]
            unique_days = len(data["checked_dates"])
            percent = int(round(unique_days / days_in_week * 100))
            items.append(
                CategoryProgress(
                    category=cat,
                    percent=percent,
                    active_count=data["active_count"],
                    total_checkins=unique_days,
                    total_duration=days_in_week,
                )
            )
        return CategoryProgressResponse(items=items)

    # ── 주간 감정 ─────────────────────────────────────────────────────────────

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

    # ── 체크인 롤백 (내부 헬퍼) ──────────────────────────────────────────────

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
        await self._eggs.rollback_checkin(uc.user_id)
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
