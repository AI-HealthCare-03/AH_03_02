"""검사 수치 기록장 서비스 레이어.

RecordService와 분리된 독립 서비스로, 검사 수치 저장·조회·지표 설정·
MONITORING 챌린지 자동 체크인을 담당한다.
"""

from datetime import date

from fastapi import HTTPException
from starlette import status

from app.dtos.lab import (
    LabPoint,
    LabRecordResponse,
    MetricDef,
    MetricOverview,
    MetricsResponse,
    OverviewResponse,
    SaveLabResponse,
)
from app.dtos.record import AutoCheckinResult
from app.models.challenge import (
    ChallengeCategory,
    ChallengeTrack,
    UserChallenge,
    UserChallengeProfile,
    UserChallengeStatus,
)
from app.models.users import User
from app.repositories.record_repository import LabRecordRepository, UserLabMetricsRepository
from app.services.challenge import ChallengeService
from app.services.lab_reference import (
    all_metric_keys,
    default_metric_keys,
    is_valid_metric,
    metric_def,
    resolve_range,
)

# 검사 결과 면책 문구
_DISCLAIMER = "참고범위는 표시용이며 의료 진단이 아닙니다. 검사 결과 해석은 담당 의료진과 상의하세요."
_TREND_LIMIT = 5  # 최근 5회 추세
_HISTORY_FETCH = 30  # 추세·증감 계산용 조회 범위


class LabService:
    """검사 수치 기록장 비즈니스 로직 서비스."""

    def __init__(self) -> None:
        self._lab = LabRecordRepository()
        self._user_metrics = UserLabMetricsRepository()
        self._challenge = ChallengeService()

    # ── 내부 헬퍼 ──────────────────────────────────────────────────────

    async def _track_of(self, user_id: int) -> ChallengeTrack:
        """사용자 챌린지 프로필에서 트랙을 조회한다. 프로필 없으면 DAILY 기본값."""
        profile = await UserChallengeProfile.get_or_none(user_id=user_id)
        return profile.track if profile else ChallengeTrack.DAILY

    async def _gender_of(self, user_id: int) -> str:
        """사용자의 성별 값("MALE"/"FEMALE")을 반환한다."""
        user = await User.get(id=user_id)
        return user.gender.value

    async def _active_keys(self, user_id: int) -> list[str]:
        """사용자 맞춤 활성 지표 키 목록을 반환한다.

        저장된 설정이 있으면 유효한 키만 필터링하여 반환하고,
        없으면 트랙 기본값을 사용한다.
        """
        setting = await self._user_metrics.get(user_id)
        if setting and setting.metric_keys is not None:
            return [k for k in setting.metric_keys if is_valid_metric(k)]
        track = await self._track_of(user_id)
        return default_metric_keys(track)

    def _metric_def_dto(self, key: str, gender: str) -> MetricDef:
        """지표 키와 성별로 MetricDef DTO를 생성한다."""
        m = metric_def(key)
        rng = resolve_range(key, gender)
        low, high = rng if rng else (None, None)
        return MetricDef(key=m.key, label=m.label, unit=m.unit, decimals=m.decimals, range_low=low, range_high=high)

    # ── 지표 설정 조회·변경 ─────────────────────────────────────────────

    async def get_metrics(self, user_id: int) -> MetricsResponse:
        """활성 지표 목록 및 전체 카탈로그를 조회한다."""
        gender = await self._gender_of(user_id)
        active = await self._active_keys(user_id)
        return MetricsResponse(
            active_keys=active,
            active=[self._metric_def_dto(k, gender) for k in active],
            catalog=[self._metric_def_dto(k, gender) for k in all_metric_keys()],
        )

    async def set_metrics(self, user_id: int, metric_keys: list[str]) -> MetricsResponse:
        """사용자 활성 지표 목록을 변경하고 갱신된 목록을 반환한다.

        유효하지 않은 키가 포함되면 422 예외를 발생시킨다.
        중복 키는 순서를 유지하며 제거한다.
        """
        for k in metric_keys:
            if not is_valid_metric(k):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"알 수 없는 지표: {k}")
        # 중복 제거 (순서 유지)
        seen: list[str] = []
        for k in metric_keys:
            if k not in seen:
                seen.append(k)
        await self._user_metrics.upsert(user_id, seen)
        return await self.get_metrics(user_id)

    # ── 개요·기록 조회 ──────────────────────────────────────────────────

    async def get_overview(self, user_id: int) -> OverviewResponse:
        """활성 지표별 최신값·이전값·증감·추세 포인트를 포함한 개요를 반환한다."""
        gender = await self._gender_of(user_id)
        active = await self._active_keys(user_id)
        # 최근 _HISTORY_FETCH개 조회 (내림차순) → 오름차순으로 뒤집어 추세 계산
        records = await self._lab.recent(user_id, _HISTORY_FETCH)
        records_asc = list(reversed(records))
        metrics: list[MetricOverview] = []
        for key in active:
            m = metric_def(key)
            pts = [
                LabPoint(date=r.measured_date, value=float(r.values[key]))
                for r in records_asc
                if key in (r.values or {}) and r.values[key] is not None
            ]
            # 최근 _TREND_LIMIT개만 추세로 사용
            pts = pts[-_TREND_LIMIT:]
            latest = pts[-1].value if pts else None
            prev = pts[-2].value if len(pts) >= 2 else None
            delta = round(latest - prev, m.decimals) if (latest is not None and prev is not None) else None
            rng = resolve_range(key, gender)
            low, high = rng if rng else (None, None)
            metrics.append(
                MetricOverview(
                    key=key,
                    label=m.label,
                    unit=m.unit,
                    decimals=m.decimals,
                    latest=latest,
                    prev=prev,
                    delta=delta,
                    range_low=low,
                    range_high=high,
                    points=pts,
                )
            )
        return OverviewResponse(metrics=metrics, disclaimer=_DISCLAIMER)

    async def get_record(self, user_id: int, measured_date: date) -> LabRecordResponse:
        """특정 날짜의 검사 기록을 조회한다. 기록 없으면 has_record=False."""
        rec = await self._lab.get_by_date(user_id, measured_date)
        if rec is None:
            return LabRecordResponse(measured_date=measured_date, values={}, has_record=False)
        return LabRecordResponse(
            measured_date=rec.measured_date,
            values={k: float(v) for k, v in (rec.values or {}).items()},
            has_record=True,
        )

    # ── 기록 저장·삭제 ──────────────────────────────────────────────────

    async def save_record(self, user_id: int, measured_date: date, values: dict) -> SaveLabResponse:
        """검사 수치를 저장하고 MONITORING 챌린지 자동 체크인을 수행한다.

        - 활성 지표 외의 키는 무시한다.
        - 음수 값은 422 예외를 발생시킨다.
        - 저장 후 오늘 MONITORING 챌린지 자동 체크인을 시도한다(graceful).
        """
        active = set(await self._active_keys(user_id))
        clean: dict[str, float] = {}
        for k, v in values.items():
            # 활성 지표가 아니거나 카탈로그에 없는 키는 무시
            if k not in active or not is_valid_metric(k):
                continue
            if v < 0:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{k}: 음수 불가")
            clean[k] = float(v)
        # 유효 값이 하나도 없으면 upsert 생략(기존 날짜 기록을 빈 dict로 덮어쓰지 않음)
        if not clean:
            return SaveLabResponse(
                measured_date=measured_date,
                saved_keys=[],
                auto_checkin=AutoCheckinResult(performed=False, reason="no_valid_values"),
            )
        await self._lab.upsert(user_id, measured_date, clean)
        # 오늘 날짜로 MONITORING 챌린지 자동 체크인 시도
        auto = await self._maybe_auto_checkin_monitoring(user_id, date.today())
        return SaveLabResponse(measured_date=measured_date, saved_keys=sorted(clean.keys()), auto_checkin=auto)

    async def delete_record(self, user_id: int, measured_date: date) -> LabRecordResponse:
        """특정 날짜의 검사 기록을 삭제하고 빈 응답을 반환한다."""
        await self._lab.delete_by_date(user_id, measured_date)
        return LabRecordResponse(measured_date=measured_date, values={}, has_record=False)

    # ── MONITORING 자동 체크인 ──────────────────────────────────────────

    async def _maybe_auto_checkin_monitoring(self, user_id: int, today: date) -> AutoCheckinResult:
        """오늘 검사 기록 시 ACTIVE MONITORING 챌린지 체크인을 자동으로 수행한다.

        - MONITORING 챌린지가 없거나 이미 체크인한 경우 performed=False를 반환한다.
        - 체크인 중 예외 발생 시 graceful하게 performed=False를 반환한다(서비스 중단 방지).
        """
        try:
            uc = await UserChallenge.filter(
                user_id=user_id,
                status=UserChallengeStatus.ACTIVE,
                challenge__category=ChallengeCategory.MONITORING,
            ).first()
            if uc is None:
                return AutoCheckinResult(performed=False, reason="no_challenge")
            if uc.last_checkin_date == today:
                return AutoCheckinResult(performed=False, reason="already_checked_in")
            await self._challenge.checkin(uc.id, user_id, today)
            return AutoCheckinResult(performed=True, reason="logged")
        except Exception:
            return AutoCheckinResult(performed=False, reason="checkin_skipped")
