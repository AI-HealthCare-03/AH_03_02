from app.models.challenge import ChallengeTrack
from app.services.lab_reference import (
    all_metric_keys,
    default_metric_keys,
    is_valid_metric,
    metric_def,
    resolve_range,
)


def test_catalog_has_16():
    assert len(all_metric_keys()) == 16
    assert "potassium" in all_metric_keys()
    assert "hba1c" in all_metric_keys()


def test_track_defaults():
    assert default_metric_keys(ChallengeTrack.DIALYSIS) == [
        "potassium",
        "phosphorus",
        "hemoglobin",
        "dialysis_weight_pre",
        "dialysis_weight_post",
    ]
    assert default_metric_keys(ChallengeTrack.CKD) == [
        "egfr",
        "creatinine",
        "systolic_bp",
        "diastolic_bp",
        "proteinuria",
    ]
    assert default_metric_keys(ChallengeTrack.WELLNESS) == [
        "systolic_bp",
        "diastolic_bp",
        "weight",
        "ldl",
        "hdl",
    ]


def test_resolve_range_gender():
    assert resolve_range("hemoglobin", "MALE") == (13.5, 17.5)
    assert resolve_range("hemoglobin", "FEMALE") == (12.0, 16.0)
    assert resolve_range("creatinine", "MALE") == (0.7, 1.2)
    assert resolve_range("creatinine", "FEMALE") == (0.5, 1.0)


def test_resolve_range_bounds():
    assert resolve_range("egfr", "MALE") == (60.0, None)
    assert resolve_range("ldl", "FEMALE") == (None, 100.0)
    assert resolve_range("systolic_bp", "MALE") == (None, 130.0)
    assert resolve_range("potassium", "FEMALE") == (3.5, 5.0)
    assert resolve_range("fasting_glucose", "MALE") == (70.0, 100.0)
    assert resolve_range("postprandial_glucose", "MALE") == (90.0, 140.0)
    assert resolve_range("hba1c", "MALE") == (None, 5.7)
    assert resolve_range("hdl", "FEMALE") == (60.0, 90.0)


def test_resolve_range_none():
    assert resolve_range("proteinuria", "MALE") is None
    assert resolve_range("weight", "FEMALE") is None


def test_metric_def_and_valid():
    d = metric_def("potassium")
    assert d.label == "칼륨(K)" and d.unit == "mEq/L" and d.decimals == 1
    assert is_valid_metric("egfr") is True
    assert is_valid_metric("nope") is False
