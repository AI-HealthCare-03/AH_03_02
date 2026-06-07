import pytest

from ai_worker.schemas.ckd import CkdJob
from ai_worker.tasks import ckd_task


@pytest.mark.asyncio
async def test_handle_ckd_job(monkeypatch) -> None:  # noqa: ANN001
    captured: dict = {}

    def fake_load():
        return ("PRED", {"impute": {}}, 0.06)

    def fake_run_inference(data, ref_date, predictor, threshold, stats, egfr_override):  # noqa: ANN001
        captured["egfr_override"] = egfr_override
        captured["hc_data"] = data
        return {"ckd_risk_score": 0.0848, "app_group": "G1", "ckd_stage": "G3A", "egfr_estimated": 48.0}

    async def fake_update(health_check_id, ckd_risk_score, app_group):  # noqa: ANN001
        captured["update"] = (health_check_id, ckd_risk_score, app_group)

    monkeypatch.setattr(ckd_task, "_load", fake_load)
    monkeypatch.setattr(ckd_task.pipeline, "run_inference", fake_run_inference)
    monkeypatch.setattr(ckd_task.db, "update_prediction", fake_update)

    job = CkdJob(health_check_id=12, egfr=48.0, checked_date="2024-06-01", payload={"gender": "MALE", "age": 58})
    await ckd_task.handle_ckd_job(job)

    assert captured["egfr_override"] == 48.0
    assert captured["update"] == (12, 0.0848, "G1")
