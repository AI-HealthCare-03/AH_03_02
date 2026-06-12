"""OCR 매핑 순수함수 검증 — 콤마 파싱·유효성 범위 (CI 격리, 로컬 pytest app 금지)."""

from app.services.ocr import (
    _NUMBER_PATTERN,
    _PURE_NUMBER_RE,
    _drop_out_of_range,
    _to_float,
)


def test_to_float_comma() -> None:
    # 천단위 콤마 제거 — 중성지방 등 4자리+ 값 오류(1,200→1) 방지
    assert _to_float("1,200") == 1200.0
    assert _to_float("118") == 118.0
    assert _to_float("0.9") == 0.9
    assert _to_float("2,500.5") == 2500.5


def test_number_pattern_comma() -> None:
    m = _NUMBER_PATTERN.search("중성지방 1,200 mg/dL")
    assert m is not None
    assert m.group() == "1,200"  # 기존엔 "1"만 잡혀 1200배 오류였음


def test_number_pattern_plain() -> None:
    m = _NUMBER_PATTERN.search("공복혈당 118 mg/dL")
    assert m is not None and m.group() == "118"


def test_pure_number_re_comma() -> None:
    assert _PURE_NUMBER_RE.fullmatch("1,200")
    assert _PURE_NUMBER_RE.fullmatch("118")
    assert _PURE_NUMBER_RE.fullmatch("0.9")
    assert not _PURE_NUMBER_RE.fullmatch("1,2")  # 잘못된 콤마 위치 거부
    assert not _PURE_NUMBER_RE.fullmatch("abc")


def test_drop_out_of_range() -> None:
    mapped = {
        "weight": {"value": 5.0, "confidence": 0.9},  # 5kg 비현실 → 제거
        "height": {"value": 170.0, "confidence": 0.9},  # 정상 → 유지
        "creatinine": {"value": 0.9, "confidence": 0.9},  # 정상 → 유지
        "fasting_glucose": {"value": 9.2, "confidence": 0.9},  # 소수점 오류(<20) → 제거
        "triglycerides": {"value": 1200.0, "confidence": 0.9},  # 콤마복원 정상(20~5000) → 유지
    }
    dropped = _drop_out_of_range(mapped)
    assert "weight" not in mapped
    assert "fasting_glucose" not in mapped
    assert "height" in mapped
    assert "creatinine" in mapped
    assert "triglycerides" in mapped
    assert len(dropped) == 2


def test_drop_out_of_range_keeps_normal() -> None:
    # 모든 값이 정상 범위면 아무것도 제거하지 않음
    mapped = {
        "systolic_bp": {"value": 120.0},
        "diastolic_bp": {"value": 80.0},
        "total_cholesterol": {"value": 190.0},
        "hdl_cholesterol": {"value": 55.0},
    }
    dropped = _drop_out_of_range(mapped)
    assert dropped == []
    assert len(mapped) == 4
