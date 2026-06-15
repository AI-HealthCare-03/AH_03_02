"""식이 설문 → RAG 위험 플래그 변환 엔진 (SSOT).

변환표 D(6문항) + 충돌규칙 R1~R5 + 원칙 P1~P3.
순수함수 compute_diet_flags + DB 조회 헬퍼 load_diet_flags로 구성.
챗봇(chat.py)·리포트 가이드(ckd_publisher.py) 두 경로가 공용 호출한다.
"""

from __future__ import annotations

from dataclasses import dataclass

# LifestyleSurvey.dialysis_type이 단일 진실 — HealthCheck.dialysis_type은 검진 생성 시 미러링된 캐시 (chat.py에서 RAG 트랙으로 승격)
DIALYSIS_TO_TRACK: dict[str, str] = {
    "none": "non_dialysis",
    "hemodialysis": "hemodialysis",
    "peritoneal": "peritoneal",
    # transplant(이식)는 의도적 미매핑 → track=None (이식 식이 별도 임상검토 항목)
}

_DIAGNOSED_TRACKS = ("non_dialysis", "hemodialysis", "peritoneal")


def dialysis_to_track(dialysis_type: str | None) -> str | None:
    """투석 종류 문자열 → RAG 트랙(미매핑/None은 None)."""
    if dialysis_type is None:
        return None
    return DIALYSIS_TO_TRACK.get(str(dialysis_type))


@dataclass(frozen=True)
class DietInput:
    soup_stew_per_day: int  # Q1 나트륨
    sweet_drink_per_day: int  # Q2 당류
    fried_food_per_week: int  # Q3 지방
    vegetables_every_meal: bool  # Q4 식이섬유 (False=거의 안먹음)
    potassium_food_freq: int | None  # Q5 칼륨 (0적음/1보통/2많음, None=미응답)
    protein_food_freq: int | None  # Q6 단백질 (0적음/1보통/2많음, None=미응답)


@dataclass(frozen=True)
class DietFlagResult:
    flags: tuple[str, ...]  # 위험 플래그 (P1: 위험 응답만)
    consult_cards: tuple[str, ...]  # 결정론적 상담카드 키 (R3)
    search_hints: tuple[str, ...]  # 검색 보강 힌트


def _is_kp_target(app_group: str | None, ckd_diagnosed: bool) -> bool:
    """칼륨·단백질 문항 해당자: A(G1)·B(G2) 또는 진단자."""
    return ckd_diagnosed or app_group in ("G1", "G2")


def _flag_sodium(diet: DietInput, flags: list[str], hints: list[str]) -> None:
    """Q1 나트륨 플래그 처리."""
    if diet.soup_stew_per_day >= 3:
        flags.append("나트륨_높음")
        hints.append("저나트륨 식사법, 국·찌개 대체 식단")
    elif diet.soup_stew_per_day == 2:
        flags.append("나트륨_주의")
        hints.append("국물 줄이기 요령, 저나트륨 조리법")


def _flag_sugar(diet: DietInput, dm_diagnosed: bool, flags: list[str], hints: list[str]) -> None:
    """Q2 당류 플래그 처리. R4: 당뇨 진단 시 혈당 맥락 우선."""
    if diet.sweet_drink_per_day >= 2:
        flags.append("당류_높음")
        hints.append("당뇨 혈당 관리 식사" if dm_diagnosed else "가당음료 줄이기")
    elif diet.sweet_drink_per_day == 1:
        flags.append("당류_주의")
        hints.append("음료 대체(물·무가당 차)")


def _flag_fat(diet: DietInput, flags: list[str], hints: list[str]) -> None:
    """Q3 지방 플래그 처리."""
    if diet.fried_food_per_week >= 3:
        flags.append("포화지방_높음")
        hints.append("조리법 대체(굽기·찌기), 심혈관 건강 식사")


def _flag_potassium(
    diet: DietInput,
    *,
    kp: bool,
    app_group: str | None,
    ckd_diagnosed: bool,
    track: str | None,
    flags: list[str],
    cards: list[str],
    hints: list[str],
) -> bool:
    """Q5 칼륨 플래그 처리. potassium_consult(상담카드 활성 여부) 반환 — R1 억제에 사용."""
    if kp and diet.potassium_food_freq == 2:
        if ckd_diagnosed and track in _DIAGNOSED_TRACKS:
            cards.append("칼륨_상담")  # 고정 상담카드 (R3)
            return True
        if not ckd_diagnosed:  # A·B 미진단 → 수집만
            flags.append("칼륨_정보")
            if app_group == "G1":  # A군(eGFR<60)만 정보 1줄
                hints.append("신장 기능 저하 시 칼륨 조절 필요 가능 — 진료 상담 권유")
    return False


def _flag_fiber(
    diet: DietInput,
    *,
    ckd_diagnosed: bool,
    potassium_consult: bool,
    flags: list[str],
    hints: list[str],
) -> None:
    """Q4 식이섬유 플래그 처리. R1: 칼륨_상담 활성 시 섬유 억제."""
    if diet.vegetables_every_meal:
        return
    if not ckd_diagnosed:
        flags.append("섬유_부족")
        hints.append("채소 늘리기 일반 권고")
    elif not potassium_consult:  # 진단자 + 칼륨상담 없음
        flags.append("섬유_부족_신장")
        hints.append("채소 종류 선택은 진료 시 확인")
    # else: 진단자 + 칼륨상담 있음 → 억제(R1), 플래그 없음


def _flag_protein(
    diet: DietInput,
    *,
    kp: bool,
    ckd_diagnosed: bool,
    track: str | None,
    flags: list[str],
    cards: list[str],
    hints: list[str],
) -> None:
    """Q6 단백질 플래그 처리. 해당자만, 트랙별 반대 P2."""
    if not (kp and diet.protein_food_freq is not None):
        return
    p = diet.protein_food_freq
    if ckd_diagnosed and track == "non_dialysis":
        if p == 2:  # 많음
            flags.append("단백질_과다_의심")
            hints.append("단백질 적정 섭취 일반 정보, 정확한 양은 영양사 상담")
        # 적음(0) → 없음 (저섭취 단정 금지, P1)
    elif ckd_diagnosed and track in ("hemodialysis", "peritoneal"):
        if p == 0:  # 적음 → 부족 위험
            cards.append("단백질_부족_위험")  # 고정 상담카드 (R3)
        # 많음 → 없음 (투석은 충분 단백질 권고)
    elif not ckd_diagnosed:  # A·B 미진단 → 수집만
        flags.append("단백질_정보")


def compute_diet_flags(
    diet: DietInput,
    *,
    app_group: str | None,
    ckd_diagnosed: bool,
    track: str | None,
    dm_diagnosed: bool,
) -> DietFlagResult:
    """식이 응답 → 플래그·상담카드·검색힌트. 순수함수(변환표 D)."""
    flags: list[str] = []
    cards: list[str] = []
    hints: list[str] = []

    _flag_sodium(diet, flags, hints)
    _flag_sugar(diet, dm_diagnosed, flags, hints)
    _flag_fat(diet, flags, hints)

    kp = _is_kp_target(app_group, ckd_diagnosed)
    potassium_consult = _flag_potassium(
        diet,
        kp=kp,
        app_group=app_group,
        ckd_diagnosed=ckd_diagnosed,
        track=track,
        flags=flags,
        cards=cards,
        hints=hints,
    )
    _flag_fiber(
        diet,
        ckd_diagnosed=ckd_diagnosed,
        potassium_consult=potassium_consult,
        flags=flags,
        hints=hints,
    )
    _flag_protein(
        diet,
        kp=kp,
        ckd_diagnosed=ckd_diagnosed,
        track=track,
        flags=flags,
        cards=cards,
        hints=hints,
    )

    return DietFlagResult(flags=tuple(flags), consult_cards=tuple(cards), search_hints=tuple(hints))


async def load_diet_flags(user_id: int) -> DietFlagResult | None:
    """사용자 최신 식이설문·검진·생활습관설문 조회 → compute_diet_flags.

    식이설문이 없으면 None(플래그 없음). 챗봇·리포트 가이드 두 경로 공용.
    """
    from app.models.diet_survey import DietSurvey
    from app.models.health_check import HealthCheck
    from app.models.lifestyle_survey import LifestyleSurvey

    # 같은 날 재제출 시 최신 설문 보장 — id tiebreaker (다른 최신-조회와 정합)
    diet_row = await DietSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()
    if diet_row is None:
        return None

    hc = await HealthCheck.filter(user_id=user_id).order_by("-checked_date", "-id").first()
    ls = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()

    app_group = str(hc.app_group) if (hc and hc.app_group is not None) else None
    track = dialysis_to_track(str(hc.dialysis_type)) if (hc and hc.dialysis_type is not None) else None
    ckd_diagnosed = bool(ls.ckd_diagnosed) if ls else False
    dm_diagnosed = bool(ls.dm_diagnosed) if ls else False

    diet = DietInput(
        soup_stew_per_day=diet_row.soup_stew_per_day,
        sweet_drink_per_day=diet_row.sweet_drink_per_day,
        fried_food_per_week=diet_row.fried_food_per_week,
        vegetables_every_meal=diet_row.vegetables_every_meal,
        potassium_food_freq=diet_row.potassium_food_freq,
        protein_food_freq=diet_row.protein_food_freq,
    )
    return compute_diet_flags(
        diet,
        app_group=app_group,
        ckd_diagnosed=ckd_diagnosed,
        track=track,
        dm_diagnosed=dm_diagnosed,
    )
