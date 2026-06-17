"""CKD 모델1·2 test set 성능 평가 — 평가 3-1 (실측 지표 + 모델 비교).

학습·검증·테스트 3분할 중 **test_final_v2.csv**(학습에 미사용)로 모델1·2를 평가한다.
CKD 라벨은 불균형(양성 ≈ 4%)이므로 ROC-AUC와 함께 PR-AUC·Brier를 핵심 지표로 본다.

⚠️ AutoGluon은 Python 3.11 필요 → 학습 전용 venv에서 실행한다.

실행:
    CKD_DATA_DIR=<260520_dir> .venv-train/bin/python scripts/eval_ckd_models.py

출력: stdout 표 + docs/model-eval/result.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.ckd import config


def _metrics_at(y, proba, threshold: float) -> dict:
    """임계값 적용 시 분류 지표 (불균형이라 accuracy보다 recall/precision 중심)."""
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def evaluate(name: str, model_dir, features: list[str], test: pd.DataFrame, val: pd.DataFrame) -> dict:
    """AutoGluon predictor 로드 → test set 예측 → 임계 무관 + 임계별 지표.

    운영 임계값(Youden / Recall≥0.88)은 **val 기준**으로 산출한다(test 로 정하면 누수).
    train.py 의 compute_threshold 를 그대로 재사용해 학습 파이프라인과 동일 정책을 검증.
    """
    from autogluon.tabular import TabularPredictor  # noqa: PLC0415

    from src.ckd.train import compute_threshold  # noqa: PLC0415

    predictor = TabularPredictor.load(str(model_dir))
    thr = compute_threshold(predictor, val, features)
    thresholds = {
        "youden(val)": thr["youden_threshold"],
        f"recall>={thr['target_recall']}(val)": thr["recall_threshold"],
    }

    y = test[config.LABEL].to_numpy().astype(int)
    proba = predictor.predict_proba(test[features])[1].to_numpy()
    return {
        "model": name,
        "n_features": len(features),
        "n_test": int(len(y)),
        "positive": int(y.sum()),
        "positive_rate": round(float(y.mean()), 4),
        # 임계 무관 지표 (불균형 데이터 핵심)
        "roc_auc": round(float(roc_auc_score(y, proba)), 4),
        "pr_auc": round(float(average_precision_score(y, proba)), 4),
        "brier": round(float(brier_score_loss(y, proba)), 4),
        # val 기준 운영 임계값별 test 분류 지표
        "operating_points": {k: _metrics_at(y, proba, t) for k, t in thresholds.items()},
    }


def main() -> None:
    test = pd.read_csv(config.TEST_CSV)
    val = pd.read_csv(config.VAL_CSV)

    results = [
        evaluate("model1 (임상 마커 42피처)", config.MODEL1_DIR, config.MODEL1_FEATURES, test, val),
        evaluate("model2 (생활습관 24피처)", config.MODEL2_DIR, config.MODEL2_FEATURES, test, val),
    ]

    print(json.dumps(results, ensure_ascii=False, indent=2))

    out = config.REPO_ROOT / "docs" / "model-eval" / "result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "test_set": Path(config.TEST_CSV).name,
        "n_test": int(len(test)),
        "results": results,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
