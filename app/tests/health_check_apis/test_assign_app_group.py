"""_assign_app_group CKD 진단자 분기 검증 (PDF 검증 시나리오, CI 격리·로컬 pytest app 금지).

순수 staticmethod라 DB 미접근. 진단자 우선(CKD/DIALYSIS) + 미진단 스크리닝(G1/G2/G4).
"""

from app.models.health_check import AppGroup, DialysisType
from app.services.health_check import HealthCheckService

_assign = HealthCheckService._assign_app_group


def test_ckd_diagnosed_no_dialysis_to_ckd() -> None:
    assert _assign(70, 120, 80, 90, ckd_diagnosed=True, dialysis_type=DialysisType.NONE) == AppGroup.CKD


def test_ckd_diagnosed_dialysis_none_arg_to_ckd() -> None:
    # 투석 종류 미입력(None)도 비투석으로 간주 → CKD
    assert _assign(70, 120, 80, 90, ckd_diagnosed=True, dialysis_type=None) == AppGroup.CKD


def test_ckd_diagnosed_hemodialysis_to_dialysis() -> None:
    assert _assign(70, 120, 80, 90, ckd_diagnosed=True, dialysis_type=DialysisType.HEMODIALYSIS) == AppGroup.DIALYSIS


def test_ckd_diagnosed_peritoneal_to_dialysis() -> None:
    assert _assign(70, 120, 80, 90, ckd_diagnosed=True, dialysis_type=DialysisType.PERITONEAL) == AppGroup.DIALYSIS


def test_ckd_diagnosed_transplant_to_dialysis() -> None:
    assert _assign(70, 120, 80, 90, ckd_diagnosed=True, dialysis_type=DialysisType.TRANSPLANT) == AppGroup.DIALYSIS


def test_ckd_diagnosed_priority_over_screening() -> None:
    # 진단자는 eGFR<60·혈압/혈당 이상이어도 스크리닝(G1/G2)으로 내려가지 않음
    assert _assign(45, 140, 90, 150, ckd_diagnosed=True, dialysis_type=DialysisType.NONE) == AppGroup.CKD


def test_undiagnosed_egfr_low_to_g1() -> None:
    assert _assign(45, 120, 75, 90, ckd_diagnosed=False) == AppGroup.G1


def test_undiagnosed_high_bp_to_g2() -> None:
    assert _assign(70, 135, 75, 90, ckd_diagnosed=False) == AppGroup.G2


def test_undiagnosed_normal_to_g4() -> None:
    # 정상 → G4 (G3는 AI 워커 비동기 배정)
    assert _assign(70, 120, 75, 90, ckd_diagnosed=False) == AppGroup.G4


def test_default_args_backward_compat() -> None:
    # ckd_diagnosed/dialysis_type 생략 시 기존 미진단 동작 유지(회귀 방지)
    assert _assign(70, 120, 75, 90) == AppGroup.G4
