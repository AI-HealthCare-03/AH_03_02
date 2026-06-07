import pytest

from ai_worker.schemas.ckd import CkdJob
from ai_worker.tasks import ckd_task


@pytest.mark.asyncio
async def test_handle_ckd_job(monkeypatch) -> None:  # noqa: ANN001
    """기본 예측 흐름: risk·app_group·shap(없을 때 None) 저장 확인."""
    captured: dict = {}

    def fake_load():
        # (predictor1, predictor2, stats, threshold)
        return ("PRED1", "PRED2", {"impute": {}}, 0.06)

    def fake_run_inference(
        data, ref_date, predictor, threshold, stats, egfr_override=None, *, predictor2=None, explain=False
    ):  # noqa: ANN001
        return {"ckd_risk_score": 0.0848, "app_group": "G1", "ckd_stage": "G3A", "egfr_estimated": 48.0}

    async def fake_update(health_check_id, ckd_risk_score, app_group, shap_model1=None, shap_model2=None):  # noqa: ANN001
        captured["update"] = {
            "health_check_id": health_check_id,
            "ckd_risk_score": ckd_risk_score,
            "app_group": app_group,
            "shap_model1": shap_model1,
            "shap_model2": shap_model2,
        }

    monkeypatch.setattr(ckd_task, "_load", fake_load)
    monkeypatch.setattr(ckd_task.pipeline, "run_inference", fake_run_inference)
    monkeypatch.setattr(ckd_task.db, "update_prediction", fake_update)

    job = CkdJob(health_check_id=12, egfr=48.0, checked_date="2024-06-01", payload={"gender": "MALE", "age": 58})
    await ckd_task.handle_ckd_job(job)

    u = captured["update"]
    assert u["health_check_id"] == 12
    assert u["ckd_risk_score"] == 0.0848
    assert u["app_group"] == "G1"
    # shap 키가 없는 결과 → None 전달
    assert u["shap_model1"] is None
    assert u["shap_model2"] is None


@pytest.mark.asyncio
async def test_handle_ckd_job_with_shap(monkeypatch) -> None:  # noqa: ANN001
    """run_inference가 shap 결과를 반환할 때 update_prediction에 올바르게 전달."""
    captured: dict = {}

    def fake_load():
        return ("PRED1", "PRED2", {"impute": {}}, 0.06)

    _shap_m1 = [
        {"feature": "수축기혈압", "value": 138.0, "shap": 0.05, "note": "현재 상태: 고혈압 1기 | 미달: — | 초과: —"}
    ]
    _shap_m2 = {
        "items": [{"feature": "흡연", "value": 2.0, "shap": 0.03}],
        "lifestyle_score": 0.07,
        "peer_top_pct": 72,
        "peer_relative": "상",
    }

    def fake_run_inference(
        data, ref_date, predictor, threshold, stats, egfr_override=None, *, predictor2=None, explain=False
    ):  # noqa: ANN001
        return {
            "ckd_risk_score": 0.12,
            "app_group": "G2",
            "ckd_stage": "G3A",
            "egfr_estimated": 62.0,
            "shap_model1": _shap_m1,
            "shap_model2": _shap_m2,
        }

    async def fake_update(health_check_id, ckd_risk_score, app_group, shap_model1=None, shap_model2=None):  # noqa: ANN001
        captured["update"] = {
            "shap_model1": shap_model1,
            "shap_model2": shap_model2,
        }

    monkeypatch.setattr(ckd_task, "_load", fake_load)
    monkeypatch.setattr(ckd_task.pipeline, "run_inference", fake_run_inference)
    monkeypatch.setattr(ckd_task.db, "update_prediction", fake_update)

    job = CkdJob(health_check_id=99, egfr=None, checked_date="2024-06-01", payload={"gender": "FEMALE", "age": 52})
    await ckd_task.handle_ckd_job(job)

    u = captured["update"]
    assert u["shap_model1"] == _shap_m1
    assert u["shap_model2"] == _shap_m2


@pytest.mark.asyncio
async def test_db_update_prediction_shap_default_none(monkeypatch) -> None:  # noqa: ANN001
    """update_prediction — shap 기본값(None) 호출이 기존 호출 시그니처와 호환."""
    import inspect

    from ai_worker.core import db

    sig = inspect.signature(db.update_prediction)
    params = sig.parameters
    # shap_model1·shap_model2 파라미터가 존재하고 기본값 None이어야 함
    assert "shap_model1" in params, "shap_model1 파라미터 없음"
    assert "shap_model2" in params, "shap_model2 파라미터 없음"
    assert params["shap_model1"].default is None, f"shap_model1 기본값이 None이 아님: {params['shap_model1'].default}"
    assert params["shap_model2"].default is None, f"shap_model2 기본값이 None이 아님: {params['shap_model2'].default}"
