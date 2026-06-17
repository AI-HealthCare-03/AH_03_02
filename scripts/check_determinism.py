"""CKD 모델 추론 결정론 검증 — 평가 3-3 (동일 입력 결과 편차 최소화).

동일한 입력을 **N회 반복 예측**해 출력 확률의 표본 표준편차가 0인지 검증한다.
산출물(predictor·train_stats·threshold) 동결 + 전처리 순수함수 + 시드 고정으로
"동일 입력 → 동일 출력"(편차 0)을 보장함을 정량 확인한다.

※ RAG 챗봇(LLM)은 temperature=0으로 편차를 최소화하나 bit-identical 보장 대상이
   아니므로 본 검증 범위는 결정론적 ML 추론(모델1·2)으로 한정한다(ADR-0005 참조).

실행:
    CKD_DATA_DIR=<*_final_v2.csv 디렉토리> .venv-train/bin/python scripts/check_determinism.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.ckd import config

N_SAMPLES = 200  # test set 앞 N건으로 반복 검증
N_REPEATS = 20  # 동일 입력 반복 횟수


def check(name: str, model_dir, features: list[str], sample: pd.DataFrame) -> dict:
    """동일 입력을 N_REPEATS 회 예측 → 샘플별 표준편차의 최대/평균."""
    from autogluon.tabular import TabularPredictor  # noqa: PLC0415

    predictor = TabularPredictor.load(str(model_dir))
    runs = [predictor.predict_proba(sample[features])[1].to_numpy() for _ in range(N_REPEATS)]
    arr = np.vstack(runs)  # (N_REPEATS, N_SAMPLES)
    per_sample_std = arr.std(axis=0)
    max_std = float(per_sample_std.max())
    return {
        "model": name,
        "n_samples": int(len(sample)),
        "n_repeats": N_REPEATS,
        "max_std": max_std,
        "mean_std": float(per_sample_std.mean()),
        "deterministic": bool(max_std == 0.0),
    }


def main() -> None:
    test = pd.read_csv(config.TEST_CSV)
    sample = test.head(N_SAMPLES)

    results = [
        check("model1 (임상 42피처)", config.MODEL1_DIR, config.MODEL1_FEATURES, sample),
        check("model2 (생활습관 24피처)", config.MODEL2_DIR, config.MODEL2_FEATURES, sample),
    ]

    print(json.dumps(results, ensure_ascii=False, indent=2))
    all_det = all(r["deterministic"] for r in results)
    print(f"\n{'✅ 완전 결정론 (편차 0)' if all_det else '❌ 편차 발견'}")

    out = config.REPO_ROOT / "docs" / "model-eval" / "determinism.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"results": results, "all_deterministic": all_det}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
