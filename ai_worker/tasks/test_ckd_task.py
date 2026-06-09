import asyncio

import pytest

from ai_worker.schemas.ckd import CkdJob
from ai_worker.tasks import ckd_task


@pytest.fixture(autouse=True)
async def _isolate_guide_tasks(monkeypatch):  # noqa: ANN001
    """가이드 detached 태스크 격리:
    기본 _run_rag/update_guide를 무해하게 stub하고 _GUIDE_TASKS를 테스트 간 정리한다.
    개별 테스트는 자체 monkeypatch로 재정의할 수 있다(나중 setattr 우선)."""
    monkeypatch.setattr(ckd_task, "_run_rag", lambda question, ctx: "")

    async def _noop_update_guide(health_check_id, ai_guide):  # noqa: ANN001
        return None

    monkeypatch.setattr(ckd_task.db, "update_guide", _noop_update_guide)
    ckd_task._GUIDE_TASKS.clear()
    yield
    for t in list(ckd_task._GUIDE_TASKS):
        t.cancel()
    ckd_task._GUIDE_TASKS.clear()


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


# ── I-2: handle_ckd_job explain=True·predictor2 인자 전달 검증 ──────────────────


@pytest.mark.asyncio
async def test_handle_ckd_job_passes_explain_true(monkeypatch) -> None:  # noqa: ANN001
    """handle_ckd_job이 run_inference에 explain=True와 predictor2를 전달하는지 검증.

    기존 fake_run_inference는 explain/predictor2를 무시했으나,
    실제 전달 여부를 captured dict에 기록해 검증한다.
    """
    captured: dict = {}

    def fake_load():
        return ("PRED1", "PRED2", {"impute": {}}, 0.06)

    def fake_run_inference(
        data,
        ref_date,
        predictor,
        threshold,
        stats,
        egfr_override=None,
        *,
        predictor2=None,
        explain=False,
    ):  # noqa: ANN001
        # 인자 캡처 — 기존 동작도 유지
        captured["run_inference_kwargs"] = {
            "predictor2": predictor2,
            "explain": explain,
        }
        return {"ckd_risk_score": 0.05, "app_group": "G2", "ckd_stage": "G2", "egfr_estimated": 72.0}

    async def fake_update(health_check_id, ckd_risk_score, app_group, shap_model1=None, shap_model2=None):  # noqa: ANN001
        captured["update_kwargs"] = {
            "shap_model1": shap_model1,
            "shap_model2": shap_model2,
        }

    monkeypatch.setattr(ckd_task, "_load", fake_load)
    monkeypatch.setattr(ckd_task.pipeline, "run_inference", fake_run_inference)
    monkeypatch.setattr(ckd_task.db, "update_prediction", fake_update)

    job = CkdJob(health_check_id=77, egfr=72.0, checked_date="2024-06-01", payload={"gender": "MALE", "age": 50})
    await ckd_task.handle_ckd_job(job)

    # I-2-A: explain=True 전달 검증
    assert "run_inference_kwargs" in captured, "run_inference가 호출되지 않음"
    assert captured["run_inference_kwargs"]["explain"] is True, (
        f"explain=True가 전달되지 않음: {captured['run_inference_kwargs']['explain']}"
    )

    # I-2-B: predictor2 전달 검증 (None이 아닌 값이어야 함)
    assert captured["run_inference_kwargs"]["predictor2"] is not None, (
        "predictor2=None이 전달됨 — SHAP 모델2 비활성화 버그"
    )

    # I-2-C: update_prediction에 shap 인자 전달 검증
    # run_inference가 shap 키 없이 반환했으므로 None 전달 (out.get 방어)
    assert "update_kwargs" in captured, "update_prediction이 호출되지 않음"
    assert captured["update_kwargs"]["shap_model1"] is None, "shap_model1 미전달(키 없을 때 None 기대)"
    assert captured["update_kwargs"]["shap_model2"] is None, "shap_model2 미전달(키 없을 때 None 기대)"


@pytest.mark.asyncio
async def test_handle_ckd_job_passes_shap_to_update(monkeypatch) -> None:  # noqa: ANN001
    """run_inference가 shap 결과를 반환할 때 update_prediction에 올바르게 전달되는지 검증.

    explain=True·predictor2 인자 전달 + update shap 전달을 통합 확인.
    """
    captured: dict = {}

    _shap_m1 = [{"feature": "수축기혈압", "value": 138.0, "shap": 0.04, "note": "현재 상태: 정상 | 미달: — | 초과: —"}]
    _shap_m2 = {
        "items": [{"feature": "흡연", "value": 2.0, "shap": 0.02}],
        "lifestyle_score": 0.05,
        "peer_top_pct": 60,
        "peer_relative": "중",
    }

    def fake_load():
        return ("PRED_A", "PRED_B", {"impute": {}}, 0.06)

    def fake_run_inference(
        data,
        ref_date,
        predictor,
        threshold,
        stats,
        egfr_override=None,
        *,
        predictor2=None,
        explain=False,
    ):  # noqa: ANN001
        captured["run_inference_kwargs"] = {"predictor2": predictor2, "explain": explain}
        return {
            "ckd_risk_score": 0.11,
            "app_group": "G2",
            "ckd_stage": "G3A",
            "egfr_estimated": 58.0,
            "shap_model1": _shap_m1,
            "shap_model2": _shap_m2,
        }

    async def fake_update(health_check_id, ckd_risk_score, app_group, shap_model1=None, shap_model2=None):  # noqa: ANN001
        captured["update_kwargs"] = {"shap_model1": shap_model1, "shap_model2": shap_model2}

    monkeypatch.setattr(ckd_task, "_load", fake_load)
    monkeypatch.setattr(ckd_task.pipeline, "run_inference", fake_run_inference)
    monkeypatch.setattr(ckd_task.db, "update_prediction", fake_update)

    job = CkdJob(health_check_id=88, egfr=58.0, checked_date="2024-06-01", payload={"gender": "FEMALE", "age": 55})
    await ckd_task.handle_ckd_job(job)

    # explain=True·predictor2 전달 확인
    ri = captured["run_inference_kwargs"]
    assert ri["explain"] is True, f"explain=True 미전달: {ri['explain']}"
    assert ri["predictor2"] is not None, "predictor2=None 전달 버그"

    # shap 결과가 update_prediction에 그대로 전달되었는지 확인
    u = captured["update_kwargs"]
    assert u["shap_model1"] == _shap_m1, "shap_model1이 update_prediction에 올바르게 전달되지 않음"
    assert u["shap_model2"] == _shap_m2, "shap_model2이 update_prediction에 올바르게 전달되지 않음"


@pytest.mark.asyncio
async def test_handle_ckd_job_spawns_guide(monkeypatch) -> None:  # noqa: ANN001
    """SHAP 저장 후 가이드 선생성 태스크가 떠 update_guide를 호출하고,
    user_ctx(eGFR·weight)와 질문이 _run_rag에 전달되는지 검증."""
    captured: dict = {}

    def fake_load():
        return ("PRED1", "PRED2", {"impute": {}}, 0.06)

    def fake_run_inference(
        data, ref_date, predictor, threshold, stats, egfr_override=None, *, predictor2=None, explain=False
    ):  # noqa: ANN001
        return {
            "ckd_risk_score": 0.1,
            "app_group": "G2",
            "ckd_stage": "G3A",
            "egfr_estimated": 58.0,
            "shap_model1": [{"feature": "수축기혈압", "value": 138.0, "shap": 0.05}],
            "shap_model2": {"items": [{"feature": "흡연", "value": 2.0, "shap": 0.03}], "lifestyle_score": 0.07},
        }

    async def fake_update_prediction(health_check_id, ckd_risk_score, app_group, shap_model1=None, shap_model2=None):  # noqa: ANN001
        pass

    async def fake_update_guide(health_check_id, ai_guide):  # noqa: ANN001
        captured["guide"] = {"health_check_id": health_check_id, "ai_guide": ai_guide}

    def fake_run_rag(question, ctx):  # noqa: ANN001
        captured["rag"] = {"question": question, "ctx": ctx}
        return "AI 가이드 본문"

    monkeypatch.setattr(ckd_task, "_load", fake_load)
    monkeypatch.setattr(ckd_task.pipeline, "run_inference", fake_run_inference)
    monkeypatch.setattr(ckd_task.db, "update_prediction", fake_update_prediction)
    monkeypatch.setattr(ckd_task.db, "update_guide", fake_update_guide)
    monkeypatch.setattr(ckd_task, "_run_rag", fake_run_rag)

    job = CkdJob(
        health_check_id=42,
        egfr=58.0,
        checked_date="2024-06-01",
        payload={"gender": "MALE", "age": 58, "weight": 70.0},
    )
    await ckd_task.handle_ckd_job(job)
    await asyncio.gather(*ckd_task._GUIDE_TASKS)  # 떼어진 가이드 태스크 완료 대기

    assert "guide" in captured, "update_guide 미호출 (가이드 태스크 미실행)"
    assert captured["guide"]["health_check_id"] == 42
    assert captured["guide"]["ai_guide"] == "AI 가이드 본문"
    assert captured["rag"]["ctx"] == {"eGFR": 58.0, "weight": 70.0}
    assert "수축기혈압" in captured["rag"]["question"]
