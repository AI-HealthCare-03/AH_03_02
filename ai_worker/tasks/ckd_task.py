"""CKD 예측 작업 핸들러 — CkdJob → run_inference → health_checks UPDATE.

predictor·train 통계·threshold는 모듈 레벨에서 1회 로드 후 상주한다
(AutoGluon predictor 로드가 무거우므로 job마다 재로드하지 않는다).
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

from ai_worker.core import db
from ai_worker.core.logger import setup_logger
from ai_worker.schemas.ckd import CkdJob
from src.ckd import artifacts, pipeline, predict
from src.ckd import config as ckd_config

logger = setup_logger("ckd_task")

_predictor = None
_predictor2 = None
_stats: dict | None = None
_threshold: float | None = None


def _load():
    """predictor1·2·stats·threshold 1회 로드(상주). 반환: (predictor1, predictor2, stats, threshold)."""
    global _predictor, _predictor2, _stats, _threshold
    if _predictor is None:
        p1, p2 = predict.load_predictors()
        _predictor = p1
        _predictor2 = p2
        _stats = artifacts.load_train_stats()
        _threshold = json.loads(ckd_config.THRESHOLD_PATH.read_text(encoding="utf-8"))["recall_threshold"]
    return _predictor, _predictor2, _stats, _threshold


async def handle_ckd_job(job: CkdJob) -> None:
    """예측 후 health_checks를 갱신. 실패는 로그로 남기고 예외를 다시 올린다(호출부에서 ack)."""
    predictor, predictor2, stats, threshold = await asyncio.to_thread(_load)
    ref = date.fromisoformat(job.checked_date)
    out = await asyncio.to_thread(
        lambda: pipeline.run_inference(
            job.payload,
            ref,
            predictor,
            threshold,
            stats,
            job.egfr,
            predictor2=predictor2,
            explain=True,
        )
    )
    await db.update_prediction(
        health_check_id=job.health_check_id,
        ckd_risk_score=out["ckd_risk_score"],
        app_group=out["app_group"],
        shap_model1=out.get("shap_model1"),
        shap_model2=out.get("shap_model2"),
    )
    logger.info(
        "ckd 예측 완료 hc=%s risk=%.4f group=%s shap_m1=%s shap_m2=%s",
        job.health_check_id,
        out["ckd_risk_score"],
        out["app_group"],
        "ok" if out.get("shap_model1") else "none",
        "ok" if out.get("shap_model2") else "none",
    )
