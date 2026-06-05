"""CKD 예측 모델 결합 — 전역 설정 (단일 진실 공급원, SSOT).

팀원 노트북(`CKD_통합_최종.ipynb` + `CKD_preprocessing_EDA_v4.ipynb`)의
피처·전처리 사양을 서비스 결합용으로 **동결**한다.
학습(train)과 서비스(serve)가 이 한 파일을 공유함으로써 train/serve skew를 차단한다.

⚠️ 데이터·모델 바이너리는 git에 올리지 않는다(외부 스토리지 + 환경변수 주입).
   여기에는 "값을 가리키는 경로·상수"만 둔다.
"""

from __future__ import annotations

import os
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# 경로 — 데이터/모델은 git 제외이므로 환경변수 우선, 기본값은 repo/data(ckd)
# ──────────────────────────────────────────────────────────────────────
# src/ckd/config.py → parents[0]=ckd, [1]=src, [2]=repo root
REPO_ROOT = Path(__file__).resolve().parents[2]

# 학습셋(*_final_v2.csv) 디렉토리 — train 통계 동결·검증에 사용 (서비스 런타임 불참)
CKD_DATA_DIR = Path(os.environ.get("CKD_DATA_DIR", REPO_ROOT / "data" / "ckd"))
TRAIN_CSV = CKD_DATA_DIR / "train_final_v2.csv"
VAL_CSV = CKD_DATA_DIR / "val_final_v2.csv"
TEST_CSV = CKD_DATA_DIR / "test_final_v2.csv"

# 모델 아티팩트(AutoGluon predictor) + 동결 통계(json) 디렉토리
CKD_ARTIFACT_DIR = Path(os.environ.get("CKD_ARTIFACT_DIR", REPO_ROOT / "models" / "ckd"))
MODEL1_DIR = CKD_ARTIFACT_DIR / "model1"  # AutoGluon TabularPredictor 디렉토리
MODEL2_DIR = CKD_ARTIFACT_DIR / "model2"
TRAIN_STATS_PATH = CKD_ARTIFACT_DIR / "train_stats.json"  # win_bounds·대치값 동결
THRESHOLD_PATH = CKD_ARTIFACT_DIR / "threshold.json"  # Youden/recall threshold

# ──────────────────────────────────────────────────────────────────────
# 타겟·라벨
# ──────────────────────────────────────────────────────────────────────
LABEL = "ckd_label"

# ──────────────────────────────────────────────────────────────────────
# 모델 입력 피처 (노트북 FEATURE_COLS / FEATURES 그대로 동결)
# ──────────────────────────────────────────────────────────────────────
# 모델1 — 임상 마커 풍부 사용자용 (42개)
MODEL1_FEATURES: list[str] = [
    "age",
    "gender",
    "bmi",
    "waist_cm",
    "sbp",
    "dbp",
    "fasting_glucose",
    "total_cholesterol",
    "hdl_cholesterol",
    "ldl_cholesterol",
    "triglycerides",
    "ast",
    "alt",
    "hemoglobin",
    "urine_protein_qual",
    "urine_glucose",
    "htn_diagnosed",
    "smoking_current",
    "family_dm",
    "family_htn",
    "family_dyslipidemia",
    "family_ihd",
    "family_stroke",
    "dm_diagnosed",
    "dyslipidemia_diagnosed",
    "marital",
    "ldl_is_estimated",
    "ast_log",
    "alt_log",
    "anemia",
    "tc_hdl_ratio",
    "tg_hdl_ratio",
    "non_hdl",
    "bp_status",
    "glucose_status",
    "pulse_pressure",
    "height_cm",
    "weight_kg",
    "fasting_glucose_log",
    "triglycerides_log",
    "abdominal_obesity",
    "tg_hdl_ratio_v2",
]

# 모델2 — 생활습관 중심 (혈압·혈당·creatinine·egfr 없음, 검진 정보 적은 사용자용, 24개)
MODEL2_FEATURES: list[str] = [
    "bmi",
    "waist_cm",
    "hdl_cholesterol",
    "ldl_cholesterol",
    "triglycerides",
    "ast",
    "alt",
    "hemoglobin",
    "age",
    "gender",
    "smoking_current",
    "family_dm",
    "family_htn",
    "family_dyslipidemia",
    "family_ihd",
    "family_stroke",
    "vigorous_days",
    "moderate_days",
    "sitting_hours",
    "walking_days",
    "activity_collected",
    "triglycerides_log",
    "ast_log",
    "alt_log",
]

# 그룹 배정 전용 — 모델 입력에서 제외(데이터 누수 방지), app_group 라우팅에만 사용
GROUP_COLS: list[str] = ["creatinine", "egfr"]

# ──────────────────────────────────────────────────────────────────────
# 결측 대치 정책 (노트북② cell 17~20)
# ──────────────────────────────────────────────────────────────────────
# 연령군 경계 — 결측 대치 층화 기준 (노트북② age_group)
AGE_GROUP_BREAKS: list[tuple[int, str]] = [
    (50, "40s"),
    (60, "50s"),
    (70, "60s"),
    (80, "70s"),  # 그 외 "80+"
]
AGE_GROUP_DEFAULT = "80+"

# gender × 연령군 중앙값으로 대치하는 연속형 컬럼 (GA_COLS)
IMPUTE_GENDER_AGE_MEDIAN: list[str] = [
    "height_cm",
    "weight_kg",
    "bmi",
    "waist_cm",
    "sbp",
    "dbp",
    "fasting_glucose",
    "total_cholesterol",
    "hdl_cholesterol",
    "ldl_cholesterol",
    "triglycerides",
    "ast",
    "alt",
    "hemoglobin",
    "urine_protein_qual",
    "urine_glucose",
    "walking_days",
]
# 연령군 중앙값만으로 대치 (성별 차이 0% 확인된 컬럼, AGE_COLS)
IMPUTE_AGE_MEDIAN: list[str] = ["sitting_hours"]
# 최빈값(mode) 대치 — 범주형 (MODE_COLS)
IMPUTE_MODE: list[str] = [
    "htn_diagnosed",
    "dm_diagnosed",
    "dyslipidemia_diagnosed",
    "smoking_current",
    "drinking_freq",
    "marital",
    "family_dm",
    "family_htn",
    "family_dyslipidemia",
    "family_ihd",
    "family_stroke",
]

# 구조적 결측(2011~2013 신체활동 미수집) → 0으로 채우는 컬럼
PA_STRUCTURAL_ZERO: list[str] = [
    "vigorous_days",
    "vigorous_hours",
    "moderate_days",
    "moderate_hours",
    "sitting_hours",
]

# ──────────────────────────────────────────────────────────────────────
# Winsorization 정책 (노트북② cell 30~32)
# ──────────────────────────────────────────────────────────────────────
# 대상 컬럼 (WIN_COLS) — 왜도 > THRESHOLD면 우측만(p99), 아니면 양측(p0.5/p99.5)
WINSOR_COLS: list[str] = [
    "sbp",
    "dbp",
    "height_cm",
    "weight_kg",
    "bmi",
    "waist_cm",
    "fasting_glucose",
    "total_cholesterol",
    "hdl_cholesterol",
    "ldl_cholesterol",
    "triglycerides",
    "ast",
    "alt",
    "hemoglobin",
    "creatinine",
    "sitting_hours",
    "walking_days",
    "vigorous_hours",
    "moderate_hours",
    "vigorous_days",
]
WINSOR_SKEW_THRESHOLD = 1.0
WINSOR_SYM_QUANTILES = (0.005, 0.995)  # 양측
WINSOR_RIGHT_QUANTILE = 0.99  # 우측만

# ──────────────────────────────────────────────────────────────────────
# 로그 변환 (노트북② cell 33) — Winsorization 이후 적용, log1p
# ──────────────────────────────────────────────────────────────────────
LOG_COLS: list[str] = ["fasting_glucose", "triglycerides", "ast", "alt"]

# ──────────────────────────────────────────────────────────────────────
# eGFR (CKD-EPI 2021 race-free) + CKD 라벨/그룹 임계
# ──────────────────────────────────────────────────────────────────────
# gender 인코딩 주의: 원시(KNHANES)는 1=남/2=여, 노트북②에서 1=남/0=여로 재인코딩
EGFR_THRESHOLD_CKD = 60  # eGFR < 60 → CKD (Stage 3+)

# CKD-EPI 2021 상수 (성별별 kappa, alpha)
EGFR_CONST = 142.0
EGFR_AGE_FACTOR = 0.9938
EGFR_FEMALE = {"kappa": 0.7, "alpha": -0.241, "factor": 1.012}  # ×1.012 (여성 보정)
EGFR_MALE = {"kappa": 0.9, "alpha": -0.302, "factor": 1.0}
EGFR_HIGH_EXP = -1.200  # scr > kappa 구간 지수
