"""diet_flags 순수함수 변환표 검증 (CI 격리 실행, 로컬 pytest app 금지)."""

from app.services.diet_flags import DietInput, compute_diet_flags, dialysis_to_track


def test_sodium_high() -> None:
    r = compute_diet_flags(
        DietInput(3, 0, 0, True, None, None),
        app_group="G4",
        ckd_diagnosed=False,
        track=None,
        dm_diagnosed=False,
    )
    assert "나트륨_높음" in r.flags


def test_sugar_high_diabetes_context() -> None:
    r = compute_diet_flags(
        DietInput(0, 2, 0, True, None, None),
        app_group="G2",
        ckd_diagnosed=False,
        track=None,
        dm_diagnosed=True,
    )
    assert "당류_높음" in r.flags
    assert any("혈당" in h for h in r.search_hints)


def test_potassium_consult_suppresses_fiber() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, False, 2, None),
        app_group=None,
        ckd_diagnosed=True,
        track="hemodialysis",
        dm_diagnosed=False,
    )
    assert "칼륨_상담" in r.consult_cards
    assert "섬유_부족_신장" not in r.flags  # R1 억제


def test_fiber_low_diagnosed_no_potassium() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, False, 0, None),
        app_group=None,
        ckd_diagnosed=True,
        track="non_dialysis",
        dm_diagnosed=False,
    )
    assert "섬유_부족_신장" in r.flags


def test_protein_excess_non_dialysis() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, None, 2),
        app_group=None,
        ckd_diagnosed=True,
        track="non_dialysis",
        dm_diagnosed=False,
    )
    assert "단백질_과다_의심" in r.flags


def test_protein_deficit_dialysis_card() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, None, 0),
        app_group=None,
        ckd_diagnosed=True,
        track="peritoneal",
        dm_diagnosed=False,
    )
    assert "단백질_부족_위험" in r.consult_cards


def test_protein_high_dialysis_no_flag() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, None, 2),
        app_group=None,
        ckd_diagnosed=True,
        track="hemodialysis",
        dm_diagnosed=False,
    )
    assert not r.flags and not r.consult_cards


def test_cd_group_no_potassium_protein() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, 2, 2),
        app_group="G4",
        ckd_diagnosed=False,
        track=None,
        dm_diagnosed=False,
    )
    assert not r.flags and not r.consult_cards


def test_p1_all_good_empty() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, 0, 1),
        app_group="G4",
        ckd_diagnosed=False,
        track=None,
        dm_diagnosed=False,
    )
    assert not r.flags and not r.consult_cards and not r.search_hints


def test_sodium_caution_boundary() -> None:
    """나트륨 2그릇 경계 → 주의(높음 아님)."""
    r = compute_diet_flags(
        DietInput(2, 0, 0, True, None, None),
        app_group="G4",
        ckd_diagnosed=False,
        track=None,
        dm_diagnosed=False,
    )
    assert "나트륨_주의" in r.flags
    assert "나트륨_높음" not in r.flags


def test_protein_normal_non_dialysis_no_flag() -> None:
    """비투석 진단자 단백질 보통(1) → 플래그 없음 (저섭취·과다 단정 금지)."""
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, None, 1),
        app_group=None,
        ckd_diagnosed=True,
        track="non_dialysis",
        dm_diagnosed=False,
    )
    assert not r.flags and not r.consult_cards


def test_transplant_diagnosed_no_potassium_card() -> None:
    """이식 진단자(track=None)는 칼륨 많음이어도 상담카드 미발행 (의도적 보수)."""
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, 2, None),
        app_group=None,
        ckd_diagnosed=True,
        track=None,
        dm_diagnosed=False,
    )
    assert "칼륨_상담" not in r.consult_cards


def test_dialysis_to_track() -> None:
    assert dialysis_to_track("hemodialysis") == "hemodialysis"
    assert dialysis_to_track("none") == "non_dialysis"
    assert dialysis_to_track("transplant") is None  # 이식 미매핑
    assert dialysis_to_track(None) is None
