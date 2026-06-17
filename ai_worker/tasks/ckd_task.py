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
from ai_worker.tasks import consult_cards, guide
from src.ckd import artifacts, pipeline, predict
from src.ckd import config as ckd_config

logger = setup_logger("ckd_task")

# 가이드 선생성 detached 태스크 참조 보관(GC 방지)
_GUIDE_TASKS: set[asyncio.Task] = set()


def _run_rag(question: str, user_context: dict) -> str:
    """RAG 그래프 동기 실행 — heavy import 격리(to_thread에서 호출)."""
    from ai_worker import rag  # noqa: PLC0415 — heavy 의존성 lazy import

    return rag.run(question, user_context)


async def _gen_and_store_guide(
    health_check_id: int,
    shap_model1: list | None,
    shap_model2: dict | None,
    user_context: dict,
) -> None:
    """가이드 1회 생성 후 ai_guide 저장. 실패는 로그만(ai_guide null 유지)."""
    try:
        diet = user_context.get("diet_flags") or {}
        question = guide.build_guide_question(shap_model1 or [], shap_model2, diet.get("search_hints"))
        text = await asyncio.to_thread(_run_rag, question, user_context)
        cards = consult_cards.render(diet.get("consult_cards"))
        final = (text or "").strip()
        if cards:
            final = f"{final}\n\n{cards}".strip()
        await db.update_guide(health_check_id, final)
        logger.info("가이드 선생성 완료 hc=%s len=%d", health_check_id, len(final))
    except Exception:  # noqa: BLE001 — 선생성 실패가 worker를 막지 않도록
        logger.exception("가이드 선생성 실패 hc=%s", health_check_id)


def _spawn_guide_task(job: CkdJob, out: dict) -> None:  # noqa: C901
    """SHAP 저장 직후 가이드 생성을 비차단 detached 태스크로 띄운다."""
    user_ctx: dict = {}
    egfr = out.get("egfr_estimated")
    if egfr is None:
        egfr = job.egfr
    if egfr is not None:
        user_ctx["eGFR"] = egfr
    weight = (job.payload or {}).get("weight")
    if weight is not None:
        user_ctx["weight"] = weight
    diet_flags = (job.payload or {}).get("diet_flags")
    if diet_flags:
        user_ctx["diet_flags"] = diet_flags
    track = (job.payload or {}).get("track")
    if track:
        user_ctx["track"] = track
    smoking = (job.payload or {}).get("smoking_status")
    if smoking:
        user_ctx["smoking_status"] = smoking
    height = (job.payload or {}).get("height")
    if height is not None:
        user_ctx["height"] = height
    gender = (job.payload or {}).get("gender")
    if gender is not None:
        user_ctx["gender"] = gender
    age = (job.payload or {}).get("age")
    if age is not None:
        user_ctx["age"] = age
    app_group = out.get("app_group")
    if app_group is not None:
        user_ctx["app_group"] = app_group

    task = asyncio.create_task(
        _gen_and_store_guide(
            job.health_check_id,
            out.get("shap_model1"),
            out.get("shap_model2"),
            user_ctx,
        )
    )
    _GUIDE_TASKS.add(task)
    task.add_done_callback(_GUIDE_TASKS.discard)


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
    _spawn_guide_task(job, out)
