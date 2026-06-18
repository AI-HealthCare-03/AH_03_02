"""검사 수치 지표 카탈로그 (Single Source of Truth).

기획서 §2-7 "검사 수치 기록장" 트랙별 지표 + 정상 범위 참고값 표 근거.
참고범위는 표시 전용이며 의료 진단이 아니다.
"""

from dataclasses import dataclass

from app.models.challenge import ChallengeTrack


@dataclass(frozen=True)
class LabMetric:
    key: str
    label: str
    unit: str
    decimals: int
    # gender("MALE"/"FEMALE") 또는 "*"(공통) → (low, high). 한쪽 None=무한. ranges=None → 참고범위 없음.
    ranges: dict[str, tuple[float | None, float | None]] | None


_CATALOG: dict[str, LabMetric] = {}


def _m(key: str, label: str, unit: str, decimals: int, ranges=None) -> None:
    """카탈로그에 지표를 등록하는 내부 헬퍼."""
    _CATALOG[key] = LabMetric(key=key, label=label, unit=unit, decimals=decimals, ranges=ranges)


# ── 투석 트랙 전용 지표 ──────────────────────────────────────────────
_m("potassium", "칼륨(K)", "mEq/L", 1, {"*": (3.5, 5.0)})
_m("phosphorus", "인(P)", "mg/dL", 1, {"*": (2.5, 4.5)})
_m("hemoglobin", "헤모글로빈", "g/dL", 1, {"MALE": (13.5, 17.5), "FEMALE": (12.0, 16.0)})
_m("dialysis_weight_pre", "투석 전 체중", "kg", 1, None)
_m("dialysis_weight_post", "투석 후 체중", "kg", 1, None)

# ── CKD 트랙 전용 지표 ───────────────────────────────────────────────
_m("egfr", "eGFR", "mL/min/1.73㎡", 0, {"*": (60.0, None)})
_m("creatinine", "크레아티닌", "mg/dL", 2, {"MALE": (0.7, 1.2), "FEMALE": (0.5, 1.0)})
_m("proteinuria", "단백뇨", "mg/dL", 1, None)

# ── 혈압·혈당·혈중지질 (공통 지표) ──────────────────────────────────
_m("systolic_bp", "수축기혈압", "mmHg", 0, {"*": (None, 130.0)})
_m("diastolic_bp", "이완기혈압", "mmHg", 0, {"*": (None, 80.0)})
_m("fasting_glucose", "공복혈당", "mg/dL", 0, {"*": (70.0, 100.0)})
_m("postprandial_glucose", "식후혈당", "mg/dL", 0, {"*": (90.0, 140.0)})
_m("hba1c", "HbA1c", "%", 1, {"*": (None, 5.7)})
_m("ldl", "LDL", "mg/dL", 0, {"*": (None, 100.0)})
_m("hdl", "HDL", "mg/dL", 0, {"*": (60.0, 90.0)})
_m("weight", "체중", "kg", 1, None)


# ── 트랙별 기본 표시 지표 (ordered list) ────────────────────────────
_TRACK_DEFAULTS: dict[ChallengeTrack, list[str]] = {
    ChallengeTrack.DIALYSIS: [
        "potassium",
        "phosphorus",
        "hemoglobin",
        "dialysis_weight_pre",
        "dialysis_weight_post",
    ],
    ChallengeTrack.CKD: [
        "egfr",
        "creatinine",
        "systolic_bp",
        "diastolic_bp",
        "proteinuria",
    ],
    ChallengeTrack.INTENSIVE: [
        "systolic_bp",
        "diastolic_bp",
        "fasting_glucose",
        "postprandial_glucose",
        "hba1c",
        "ldl",
        "hdl",
    ],
    ChallengeTrack.DAILY: [
        "systolic_bp",
        "diastolic_bp",
        "fasting_glucose",
        "postprandial_glucose",
        "hba1c",
        "ldl",
        "hdl",
    ],
    ChallengeTrack.WELLNESS: [
        "systolic_bp",
        "diastolic_bp",
        "weight",
        "ldl",
        "hdl",
    ],
}


def all_metric_keys() -> list[str]:
    """카탈로그에 등록된 모든 지표 키 목록을 반환한다."""
    return list(_CATALOG.keys())


def is_valid_metric(key: str) -> bool:
    """주어진 키가 카탈로그에 존재하는지 확인한다."""
    return key in _CATALOG


def metric_def(key: str) -> LabMetric:
    """지표 키로 LabMetric 정의를 반환한다. 없으면 KeyError."""
    return _CATALOG[key]


def default_metric_keys(track: ChallengeTrack) -> list[str]:
    """트랙에 따른 기본 표시 지표 키 목록을 반환한다. 매핑 없으면 DAILY 기본값."""
    return list(_TRACK_DEFAULTS.get(track, _TRACK_DEFAULTS[ChallengeTrack.DAILY]))


def resolve_range(key: str, gender: str) -> tuple[float | None, float | None] | None:
    """지표·성별의 참고범위 (low, high) 튜플을 반환한다.

    - 지표가 없거나 ranges=None 이면 None 반환.
    - 성별 일치 항목이 없으면 공통("*") 항목을 사용한다.
    """
    m = _CATALOG.get(key)
    if m is None or m.ranges is None:
        return None
    # 키 존재 여부로 명시 분기 ("키 없음"과 (None, None) 범위를 구분 — or 폴백 footgun 회피)
    result = m.ranges.get(gender)
    if result is None:
        result = m.ranges.get("*")
    return result
