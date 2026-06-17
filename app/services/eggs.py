"""알 → 3단계 진화 시스템 서비스.

명세 v3 (2026-06-01 갱신): 단일 알을 3단계까지 키우는 구조.

진화 흐름:
  체크인 0~9회   → 알 🥚 (stage=0)
  체크인 10회 도달 → 부화! 1단계 캐릭터 등장 (종 추첨 + 이름 생성)
  체크인 40회 도달 → 2단계 진화
  체크인 100회 도달 → 3단계 최종 진화 (완료, 새 알 자동 시작 X)

진화 보너스: +100 / +400 / +750 pt (균형 분배, 합 1,250pt)
Goal Gradient 알림: 90회(=3단계 임박, 90%) 도달 시 1회.

DB 필드 재활용 (스키마 변경 없이 의미만 재정의):
  stage_25_bonus_paid   → HATCH_AT(10) 보너스 지급됨
  stage_50_bonus_paid   → EVOLVE_2(40) 진화 보너스 지급됨
  stage_75_bonus_paid   → EVOLVE_3(100) 최종 진화 보너스 지급됨
  stage_100_bonus_paid  → 미사용 (legacy, 향후 부활 여지)
  goal_90_alerted       → 90회 알림 발송됨
  goal_70_alerted       → 미사용 (legacy)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.utils.character_names import generate_name, pick_species
from app.models.gamification import CharacterSpecies, PointReason
from app.models.notification import NotificationType
from app.repositories.gamification_repository import EggRepository, PointRepository
from app.repositories.notification_repository import NotificationRepository

# 진화 임계값 (누적 체크인)
HATCH_AT = 10
EVOLVE_2 = 40
EVOLVE_3 = 100

# 최종 진화 시점 (= 진행률 100% 기준)
GOAL_CHECKINS = EVOLVE_3

# Goal Gradient 알림 (최종 진화 임박, 90%)
GOAL_GRADIENT_FINAL = 90

# 진화 테이블: (임계, 단계번호, 보너스pt, DB flag 이름)
EVOLUTION_TABLE: list[tuple[int, int, int, str]] = [
    (HATCH_AT, 1, 100, "stage_25_bonus_paid"),
    (EVOLVE_2, 2, 400, "stage_50_bonus_paid"),
    (EVOLVE_3, 3, 750, "stage_75_bonus_paid"),
]

SPECIES_LABEL: dict[CharacterSpecies, str] = {
    CharacterSpecies.TURTLE: "🐢 거북이",
    CharacterSpecies.PENGUIN: "🐧 펭귄",
    CharacterSpecies.SQUIRREL: "🐿️ 다람쥐",
    CharacterSpecies.RABBIT: "🐰 토끼",
    CharacterSpecies.PANDA: "🐼 판다",
}

EVOLUTION_NAMES: dict[int, str] = {
    2: "더 자랐어요",
    3: "완전체!",
}


@dataclass
class EggUpdate:
    progress_checkins: int = 0
    current_stage: int = 0  # 0=알, 1=부화, 2=2단계, 3=완전체
    goal_70_just_alerted: bool = False  # legacy
    goal_90_just_alerted: bool = False  # 90회 알림 발동
    stage_bonus: int = 0
    stage_milestone: int = 0  # 도달한 임계 (10/40/100)
    hatched: bool = False  # 부화(1단계) 도달
    evolved_to: int | None = None  # 진화한 단계 (2/3). hatched 일 때는 None
    is_legendary: bool | None = None  # v1.0 비활성
    species: CharacterSpecies | None = None  # 부화 시 결정
    character_name: str | None = None
    new_egg_no: int | None = None  # 3단계 완료해도 새 알 자동 시작 X (None)
    extras: dict = field(default_factory=dict)


class EggService:
    def __init__(self) -> None:
        self._eggs = EggRepository()
        self._points = PointRepository()
        self._notif = NotificationRepository()

    async def progress_and_check(self, user_id: int, challenge_id: int | None = None) -> EggUpdate:
        """체크인 1회마다 호출. 진행률 +1 + 단계 전환 + 진화/부화 알림 + 보너스."""
        egg = await self._eggs.get_or_create_current(user_id)

        # 3단계 완료 상태면 freeze — 추가 체크인 효과 없음
        if egg.current_stage >= 3:
            return EggUpdate(
                progress_checkins=egg.progress_checkins,
                current_stage=egg.current_stage,
                species=egg.species,
                character_name=egg.character_name,
            )

        # 진행률 +1 (최대 GOAL_CHECKINS 까지 누적)
        if egg.progress_checkins < GOAL_CHECKINS:
            egg.progress_checkins += 1
        update = EggUpdate(progress_checkins=egg.progress_checkins)

        # 단계 계산
        new_stage = self._calc_stage(egg.progress_checkins)
        egg.current_stage = new_stage
        update.current_stage = new_stage

        # 진화 임계 도달 처리 (각 1회만)
        for threshold, stage_no, bonus, flag in EVOLUTION_TABLE:
            if egg.progress_checkins >= threshold and not getattr(egg, flag, False):
                # 보너스 적립
                await self._points.create_transaction(
                    user_id=user_id,
                    amount=bonus,
                    reason=PointReason.STAGE_BONUS,
                    extra={"egg_no": egg.egg_no, "stage": stage_no, "challenge_id": challenge_id},
                )

                if stage_no == 1:
                    # 부화 — 종 추첨 + 이름 생성
                    species = pick_species()
                    character_name = generate_name(species)
                    egg.species = species
                    egg.character_name = character_name
                    egg.hatched_at = datetime.now(UTC)
                    egg.is_legendary = False
                    species_label = SPECIES_LABEL[species]
                    await self._notif.create(
                        user_id=user_id,
                        type=NotificationType.EGG_HATCHED,
                        title=f"{species_label} 부화!",
                        message=f"'{character_name}' 가 태어났어요. 컬렉션에서 만나보세요.",
                        related_id=egg.id,
                    )
                    update.hatched = True
                    update.species = species
                    update.character_name = character_name
                else:
                    # 진화 (2/3 단계)
                    name = egg.character_name or "캐릭터"
                    headline = EVOLUTION_NAMES[stage_no]
                    await self._notif.create(
                        user_id=user_id,
                        type=NotificationType.STAGE_BONUS,
                        title=f"{headline} ({stage_no}단계)",
                        message=f"'{name}' 가 {stage_no}단계로 진화했어요! +{bonus}pt 적립.",
                        related_id=egg.id,
                    )
                    update.evolved_to = stage_no

                setattr(egg, flag, True)
                update.stage_bonus = bonus
                update.stage_milestone = threshold

        # Goal Gradient 알림 (90회 = 3단계 임박, 1회)
        if egg.progress_checkins >= GOAL_GRADIENT_FINAL and not egg.goal_90_alerted:
            remaining = GOAL_CHECKINS - egg.progress_checkins
            await self._notif.create(
                user_id=user_id,
                type=NotificationType.EGG_GOAL_90,
                title="최종 진화 임박!",
                message=f"앞으로 {remaining}번만 더 체크인하면 3단계 완성!",
                related_id=egg.id,
            )
            egg.goal_90_alerted = True
            update.goal_90_just_alerted = True

        await egg.save()
        # 3단계 도달 = 완료. 새 알 자동 시작 X. (update.new_egg_no는 None 유지)
        return update

    async def rollback_checkin(self, user_id: int) -> None:
        """체크인 1회 롤백: progress_checkins -= 1, 단계 역전 시 stage·보너스 플래그 함께 되돌림.

        _rollback_today_checkin()에서 호출된다.
        보너스 플래그를 함께 되돌리지 않으면 다음 재체크인 시 보너스가 재지급되지 않는 2차 버그 발생.
        """
        egg = await self._eggs.get_or_create_current(user_id)

        if egg.progress_checkins <= 0:
            return

        egg.progress_checkins -= 1
        new_stage = self._calc_stage(egg.progress_checkins)

        if new_stage < egg.current_stage:
            egg.current_stage = new_stage
            # 더 이상 임계값 미달인 구간의 보너스 플래그 해제
            for threshold, _stage_no, _bonus, flag in EVOLUTION_TABLE:
                if egg.progress_checkins < threshold:
                    setattr(egg, flag, False)

        await egg.save()

    @staticmethod
    def _calc_stage(progress: int) -> int:
        """0=알, 1=부화, 2=2단계, 3=3단계 최종."""
        if progress >= EVOLVE_3:
            return 3
        if progress >= EVOLVE_2:
            return 2
        if progress >= HATCH_AT:
            return 1
        return 0
