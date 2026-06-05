"""CKD train 통계·모델 아티팩트 로드 (런타임).

`train_stats.json`(win_bounds·tg_hdl_v2)을 로드해 features 변환에 주입한다.
predictor(AutoGluon) 로드는 predict.py에서 담당한다(무거운 의존성 격리).
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from . import config


@lru_cache(maxsize=1)
def load_train_stats() -> dict[str, Any]:
    """동결된 train 통계 로드. win_bounds는 apply_winsor 형식(tuple)으로 변환."""
    if not config.TRAIN_STATS_PATH.exists():
        raise FileNotFoundError(
            f"train_stats.json 없음. 먼저 train_stats.py 실행:\n"
            f"  CKD_DATA_DIR=<학습셋> uv run --group ckd python -m src.ckd.train_stats\n"
            f"  경로: {config.TRAIN_STATS_PATH}"
        )
    data = json.loads(config.TRAIN_STATS_PATH.read_text(encoding="utf-8"))
    # win_bounds: JSON list → tuple (features.apply_winsor 형식)
    data["win_bounds"] = {col: tuple(v) for col, v in data["win_bounds"].items()}
    return data
