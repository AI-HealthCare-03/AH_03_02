"""CKD 모델 학습 — train_final_v2.csv → AutoGluon predictor (오프라인 진입점).

노트북③ 학습부를 모듈화. 모델1(임상 마커)·모델2(생활습관) + threshold 동결.
입력은 가공 완료본(train/val_final_v2.csv), 출력은 predictor 디렉토리 + threshold.json.

⚠️ AutoGluon은 Python 3.11 필요(3.13 미지원). 학습 전용 venv에서 실행한다.

실행 (학습 전용 3.11 venv):
    CKD_DATA_DIR=<260520> .venv-train/bin/python -m src.ckd.train          # 전체(time_limit 3600s)
    CKD_DATA_DIR=<260520> .venv-train/bin/python -m src.ckd.train --quick   # 빠른 검증(300s)
"""

from __future__ import annotations

import argparse
import json
import random

import numpy as np
import pandas as pd

from . import config

# 재현성: 데이터 분할·샘플링 시드 고정 (학습 재현). 추론은 산출물 동결로 이미 완전
# 결정론 — scripts/check_determinism.py 가 동일 입력 N회 반복 편차 0 을 검증한다.
SEED = 42
DEFAULT_TIME_LIMIT = 3600  # 노트북③ 모델1·2 공통
TARGET_RECALL = 0.88  # 노트북③ threshold 기준


def _fit(train: pd.DataFrame, val: pd.DataFrame, features: list[str], eval_metric: str, model_dir, time_limit: int):
    """AutoGluon TabularPredictor 학습 (노트북③ 설정 동일)."""
    from autogluon.tabular import TabularDataset, TabularPredictor  # noqa: PLC0415

    cols = features + [config.LABEL]
    predictor = TabularPredictor(
        label=config.LABEL,
        eval_metric=eval_metric,
        problem_type="binary",
        path=str(model_dir),
        verbosity=2,
    ).fit(
        train_data=TabularDataset(train[cols]),
        tuning_data=TabularDataset(val[cols]),
        use_bag_holdout=True,
        presets="best_quality",
        time_limit=time_limit,
        num_bag_folds=5,
        num_bag_sets=1,
        num_stack_levels=1,
    )
    return predictor


def compute_threshold(predictor, val: pd.DataFrame, features: list[str], target_recall: float = TARGET_RECALL) -> dict:
    """val 기준 Youden + Recall≥target threshold 산출 (노트북③ Step 3)."""
    from sklearn.metrics import precision_recall_curve, roc_curve  # noqa: PLC0415

    y = val[config.LABEL].to_numpy()
    proba = predictor.predict_proba(val[features])[1].to_numpy()

    fpr, tpr, thr_roc = roc_curve(y, proba)
    youden = float(thr_roc[int(np.argmax(tpr - fpr))])

    # Recall ≥ target 을 만족하는 가장 높은 threshold (그 안에서 precision 최대)
    _, rec, thr_pr = precision_recall_curve(y, proba)
    ok = rec[:-1] >= target_recall
    recall_thr = float(thr_pr[ok].max()) if bool(ok.any()) else youden

    return {"youden_threshold": youden, "recall_threshold": recall_thr, "target_recall": target_recall}


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    ap = argparse.ArgumentParser(description="CKD AutoGluon 학습")
    ap.add_argument("--quick", action="store_true", help="빠른 검증(time_limit 300s)")
    args = ap.parse_args()
    time_limit = 300 if args.quick else DEFAULT_TIME_LIMIT

    train = pd.read_csv(config.TRAIN_CSV)
    val = pd.read_csv(config.VAL_CSV)
    config.CKD_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"데이터: train {train.shape} / val {val.shape}")

    print(f"\n[모델1] 임상 마커 {len(config.MODEL1_FEATURES)}개 학습 (time_limit={time_limit}s)")
    p1 = _fit(train, val, config.MODEL1_FEATURES, "roc_auc", config.MODEL1_DIR, time_limit)
    thr = compute_threshold(p1, val, config.MODEL1_FEATURES)
    config.THRESHOLD_PATH.write_text(json.dumps(thr, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  threshold 저장: {thr}")

    print(f"\n[모델2] 생활습관 {len(config.MODEL2_FEATURES)}개 학습 (time_limit={time_limit}s)")
    _fit(train, val, config.MODEL2_FEATURES, "average_precision", config.MODEL2_DIR, time_limit)

    print(f"\n학습 완료 → {config.MODEL1_DIR}, {config.MODEL2_DIR}")


if __name__ == "__main__":
    main()
