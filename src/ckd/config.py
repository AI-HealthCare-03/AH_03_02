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

# ──────────────────────────────────────────────────────────────────────
# 모델1 SHAP 리포트 — 사전 상수 (노트북 CELL [12] 원본 이식, SSOT)
# ──────────────────────────────────────────────────────────────────────

# _log 파생변수 → 부모 변수로 SHAP 기여도 합산 매핑
M1_LOG_PARENT: dict[str, str] = {
    "triglycerides_log": "triglycerides",
    "ast_log": "ast",
    "alt_log": "alt",
    "fasting_glucose_log": "fasting_glucose",
}

# SHAP 표시 대상 변수 (임상 수치 14개, 노트북 M1_SHAP_VARS)
M1_SHAP_VARS: list[str] = [
    "sbp",
    "dbp",
    "fasting_glucose",
    "total_cholesterol",
    "ldl_cholesterol",
    "hdl_cholesterol",
    "triglycerides",
    "ast",
    "alt",
    "hemoglobin",
    "urine_protein_qual",
    "urine_glucose",
    "waist_cm",
    "bmi",
]

# 변수 한글 라벨 (노트북 M1_LABEL)
M1_LABEL: dict[str, str] = {
    "sbp": "수축기혈압",
    "dbp": "이완기혈압",
    "pulse_pressure": "맥압",
    "fasting_glucose": "공복혈당(FBS)",
    "total_cholesterol": "총콜레스테롤",
    "ldl_cholesterol": "저밀도 지단백(LDL)",
    "hdl_cholesterol": "고밀도 지단백(HDL)",
    "triglycerides": "중성지방",
    "ast": "간 효소(AST)",
    "alt": "간 효소(ALT)",
    "hemoglobin": "헤모글로빈",
    "urine_protein_qual": "요단백",
    "urine_glucose": "요당",
    "waist_cm": "허리둘레",
    "bmi": "체질량지수(BMI, kg/m²)",
    "waist_height_ratio": "허리-키 비율",
    "creatinine": "크레아티닌",
    "smoking_current": "흡연 여부",
}

# 변수 설명 문구 (노트북 M1_DESC)
M1_DESC: dict[str, str] = {
    "sbp": "심장이 수축할 때 혈관 압력",
    "dbp": "심장이 이완할 때 혈관 압력",
    "pulse_pressure": "수축기·이완기 혈압의 차이",
    "fasting_glucose": "공복 상태에서 잰 혈당",
    "total_cholesterol": "혈액 속 전체 콜레스테롤",
    "ldl_cholesterol": "혈관에 쌓이는 나쁜 콜레스테롤",
    "hdl_cholesterol": "혈관을 청소하는 좋은 콜레스테롤",
    "triglycerides": "혈액 속 지방 성분",
    "ast": "간·근육 손상 시 오르는 효소",
    "alt": "간 손상 시 오르는 효소",
    "hemoglobin": "산소를 운반하는 적혈구 색소",
    "urine_protein_qual": "소변으로 단백질이 새는지 검사",
    "urine_glucose": "소변으로 당이 새는지 검사",
    "waist_cm": "복부(내장) 비만 지표",
    "bmi": "키 대비 체중 지표(kg/m²)",
    "waist_height_ratio": "키 대비 허리둘레 비율",
    "creatinine": "신장의 여과 기능을 나타내는 노폐물 수치",
    "smoking_current": "0=비흡연  1=과거 흡연  2=현재 흡연",
}

# 변수 이상 시 위험 질환 (미달, 초과) (노트북 M1_DISEASE)
M1_DISEASE: dict[str, tuple[str, str]] = {
    "sbp": (
        "저혈압·탈수·부신기능저하·쇼크(중증) 등 원인 점검",
        "고혈압·뇌졸중·심혈관질환·심부전·고혈압성 신증",
    ),
    "dbp": (
        "저혈압·탈수 등 원인 점검",
        "고혈압·뇌졸중·심혈관질환·심부전·고혈압성 신증",
    ),
    "pulse_pressure": (
        "심박출량 감소·심부전·대동맥판막협착",
        "동맥경화(혈관 경직)·대동맥판막역류·갑상선기능항진",
    ),
    "fasting_glucose": (
        "기아·간질환·인슐린종 등 저혈당 원인 점검",
        "당뇨병·내당능장애·공복혈당장애·당뇨병성 신증·심혈관질환",
    ),
    "total_cholesterol": (
        "영양결핍·간질환·갑상선기능항진·흡수장애",
        "이상지질혈증·동맥경화·심혈관질환",
    ),
    "ldl_cholesterol": (
        "(대개 문제 적음) 영양결핍·간질환·갑상선항진",
        "동맥경화·관상동맥질환·심혈관질환",
    ),
    "hdl_cholesterol": (
        "낮은 것 자체가 위험 → 심혈관질환·동맥경화 위험↑",
        "대체로 보호적(높을수록 유리), 극히 높으면 드문 유전적 요인",
    ),
    "triglycerides": (
        "영양결핍·갑상선기능항진·흡수장애(드묾)",
        "고중성지방혈증·대사증후군·심혈관질환·췌장염(매우 높을 때)",
    ),
    "ast": ("—", "간세포 손상(간염·지방간·간경화)·근육 손상·심근경색·알코올"),
    "alt": ("—", "간세포 손상(간염·지방간·약물성 간손상) — 간 특이도 높음"),
    "hemoglobin": (
        "철·비타민 결핍·만성질환(신장성 빈혈 등)·재생불량성·용혈성 빈혈 등 원인 점검",
        "적혈구증가증·탈수·만성 저산소(폐질환·흡연)",
    ),
    "urine_protein_qual": (
        "—",
        "신장 손상(사구체신염·당뇨병성·고혈압성 신증·CKD)·일시적(발열·운동·기립성)",
    ),
    "urine_glucose": (
        "—",
        "당뇨·고혈당 / 혈당 정상 시 신성 당뇨(세뇨관 재흡수 문제)·임신성 당뇨병",
    ),
    "waist_cm": ("저체중·영양결핍", "복부비만·인슐린저항성·대사증후군·당뇨·심혈관질환"),
    "bmi": (
        "영양결핍·근감소·면역저하·골다공증",
        "당뇨·고혈압·이상지질혈증·대사증후군·비만 관련 신증",
    ),
    "waist_height_ratio": ("—", "내장지방·대사증후군 위험"),
    "creatinine": ("—", "신장 기능 저하 → 정밀검사(CKD·신부전)"),
    "smoking_current": (
        "—",
        "심혈관질환·폐질환·암·COPD·신장 기능 저하 가속",
    ),
}

# 변수별 단계(stage) 기준 — (단위, 정상범위, 구간리스트[(lo,hi,라벨)]) 또는 성별별 dict (노트북 M1_STAGES)
M1_STAGES: dict[str, tuple] = {
    "sbp": ("mmHg", "<120", [(0, 120, "정상"), (120, 140, "주의"), (140, 9999, "위험")]),
    "dbp": ("mmHg", "<80", [(0, 80, "정상"), (80, 90, "주의"), (90, 9999, "위험")]),
    "fasting_glucose": (
        "mg/dL",
        "<100",
        [(0, 100, "정상"), (100, 126, "주의"), (126, 9999, "위험")],
    ),
    "total_cholesterol": (
        "mg/dL",
        "<200",
        [(0, 200, "적정"), (200, 240, "경계"), (240, 9999, "높음")],
    ),
    "ldl_cholesterol": (
        "mg/dL",
        "<100",
        [(0, 100, "적정"), (100, 130, "거의 적정"), (130, 160, "경계"), (160, 190, "높음"), (190, 9999, "매우 높음")],
    ),
    "hdl_cholesterol": (
        "mg/dL",
        "60~80",
        [(0, 40, "낮음"), (40, 60, "주의"), (60, 80, "적정"), (80, 9999, "높음(모니터링)")],
    ),
    "triglycerides": (
        "mg/dL",
        "<150",
        [(0, 150, "적정"), (150, 200, "경계"), (200, 500, "높음"), (500, 99999, "매우 높음")],
    ),
    "ast": ("U/L", "≤40", [(0, 41, "정상"), (41, 9999, "위험")]),
    "alt": ("U/L", "≤40", [(0, 41, "정상"), (41, 9999, "위험")]),
    "urine_protein_qual": ("", "음성", [(0, 1, "음성"), (1, 99, "양성")]),
    "urine_glucose": ("", "음성", [(0, 1, "음성"), (1, 99, "양성")]),
    "waist_cm": (
        "cm",
        {"M": "<90", "F": "<85"},
        {"M": [(0, 90, "정상"), (90, 999, "복부비만")], "F": [(0, 85, "정상"), (85, 999, "복부비만")]},
    ),
    "bmi": (
        "kg/m²",
        "18.5–22.9",
        [
            (0, 18.5, "저체중"),
            (18.5, 23, "정상"),
            (23, 25, "과체중"),
            (25, 30, "경도 비만"),
            (30, 35, "중등도 비만"),
            (35, 99, "고도 비만"),
        ],
    ),
    "pulse_pressure": (
        "mmHg",
        "40 내외",
        [(0, 40, "낮음"), (40, 60, "정상"), (60, 999, "높음")],
    ),
    "waist_height_ratio": ("", "<0.5", [(0, 0.5, "정상"), (0.5, 9, "높음")]),
    "hemoglobin": (
        "g/dL",
        {"M": "13~16.5", "F": "12~16"},
        {
            "M": [(0, 13, "빈혈"), (13, 16.5, "정상"), (16.5, 99, "높음")],
            "F": [(0, 12, "빈혈"), (12, 16, "정상"), (16, 99, "높음")],
        },
    ),
    "creatinine": (
        "mg/dL",
        "0.50~1.4",
        [(0, 0.5, "낮음"), (0.5, 1.4, "정상"), (1.4, 99, "높음")],
    ),
    "smoking_current": (
        "",
        "비흡연",
        [(0, 1, "비흡연"), (1, 2, "과거 흡연"), (2, 99, "현재 흡연")],
    ),
}

# ──────────────────────────────────────────────────────────────────────
# 모델2 SHAP 리포트 — 사전 상수 (노트북 CELL [29] 원본 이식, SSOT)
# ──────────────────────────────────────────────────────────────────────

# _log 파생변수 → 부모 변수로 SHAP 기여도 합산 매핑 (모델2용)
M2_LOG_PARENT: dict[str, str] = {
    "triglycerides_log": "triglycerides",
    "ast_log": "ast",
    "alt_log": "alt",
}

# SHAP 표시 제외 변수 (노트북 DISPLAY_EXCLUDED)
# — activity_collected(수집 여부 flag), hemoglobin(임상 전용), *_log(부모로 합산됨)
# frozenset 선언으로 _m2_filter_actionable 내 반복 in-check O(1) 보장
M2_DISPLAY_EXCLUDED: frozenset[str] = frozenset(
    [
        "activity_collected",
        "hemoglobin",
        "triglycerides_log",
        "ast_log",
        "alt_log",
    ]
)

# 배경 변수 — SHAP 표시 대상에서 제외 (나이·성별·가족력)
# frozenset 선언으로 _m2_filter_actionable 내 반복 in-check O(1) 보장
M2_BASELINE_VARS: frozenset[str] = frozenset(
    [
        "age",
        "gender",
        "family_dm",
        "family_htn",
        "family_dyslipidemia",
        "family_ihd",
        "family_stroke",
    ]
)

# 유산소 운동 관련 변수
M2_AEROBIC_VARS: list[str] = ["moderate_days", "walking_days", "vigorous_days"]

# 생활습관 도메인 분류 (노트북 DOMAIN) — lifestyle_score 계산·도메인 분류에 사용
M2_DOMAIN: dict[str, str] = {
    "ldl_cholesterol": "diet",
    "triglycerides": "diet",
    "bmi": "diet",
    "waist_cm": "diet",
    "hdl_cholesterol": "exercise",
    "sitting_hours": "exercise",
    "walking_days": "exercise",
    "moderate_days": "exercise",
    "vigorous_days": "exercise",
    "ast": "etc",
    "alt": "etc",
    "smoking_current": "etc",
}

# 변수 한글 라벨 (노트북 PLAIN_LABEL)
M2_PLAIN_LABEL: dict[str, str] = {
    "bmi": "체질량지수(BMI)",
    "waist_cm": "허리둘레",
    "hdl_cholesterol": "고밀도 지단백(HDL)",
    "ldl_cholesterol": "저밀도 지단백(LDL)",
    "triglycerides": "중성지방",
    "ast": "간 효소(AST)",
    "alt": "간 효소(ALT)",
    "sitting_hours": "하루 앉아있는 시간",
    "walking_days": "걷기(주)",
    "moderate_days": "중강도 운동(주)",
    "vigorous_days": "고강도 운동(주)",
    "smoking_current": "흡연 여부",
}

# 정상범위 매핑 (노트북 NORMAL_RANGES_MAP) — gender dict는 {'M':[lo,hi],'F':[lo,hi]}
M2_NORMAL_RANGES: dict[str, object] = {
    "bmi": [18.5, 22.9],
    "waist_cm": {"M": [0, 90], "F": [0, 85]},
    "hdl_cholesterol": [60, 90],
    "ldl_cholesterol": [0, 100],
    "triglycerides": [0, 150],
    "ast": [0, 40],
    "alt": [0, 40],
    "sitting_hours": [0, 5.999],  # stage [0,6) 와 in_normal(<=상한) 통일용
    "walking_days": [5, 99],
    "moderate_days": [5, 99],
    "vigorous_days": [3, 99],
    "smoking_current": [0, 0.5],
}

# 임상 단계 기준 (노트북 CLINICAL_STAGES) — 모델2 SHAP 리포트에서 stage 라벨 조회용
# 구조: {unit, target, stages: [(lo,hi,label,color)] 또는 성별별 dict}
M2_CLINICAL_STAGES: dict[str, dict] = {
    "bmi": {
        "unit": "",
        "target": "18.5–22.9",
        "stages": [
            (0, 18.5, "저체중", "#3498db"),
            (18.5, 23.0, "정상", "#27ae60"),
            (23.0, 25.0, "과체중", "#f39c12"),
            (25.0, 30.0, "경도 비만", "#e67e22"),
            (30.0, 35.0, "중등도 비만", "#e74c3c"),
            (35.0, 999, "고도 비만", "#c0392b"),
        ],
    },
    "waist_cm": {
        "unit": "cm",
        "target": {"M": "90 미만", "F": "85 미만"},
        "stages": {
            "M": [(0, 90, "정상", "#27ae60"), (90, 999, "복부비만", "#e74c3c")],
            "F": [(0, 85, "정상", "#27ae60"), (85, 999, "복부비만", "#e74c3c")],
        },
    },
    "hdl_cholesterol": {
        "unit": "mg/dL",
        "target": "60~90",
        "stages": [
            (0, 40, "낮음", "#e74c3c"),
            (40, 60, "주의", "#f39c12"),
            (60, 90, "적절", "#27ae60"),
            (90, 999, "높음", "#2980b9"),
        ],
    },
    "ldl_cholesterol": {
        "unit": "mg/dL",
        "target": "100 미만",
        "stages": [
            (0, 100, "적절", "#27ae60"),
            (100, 130, "거의 적절", "#2ecc71"),
            (130, 160, "약간 높음", "#f39c12"),
            (160, 190, "높음", "#e67e22"),
            (190, 999, "아주 높음", "#e74c3c"),
        ],
    },
    "triglycerides": {
        "unit": "mg/dL",
        "target": "150 미만",
        "stages": [
            (0, 150, "적정", "#27ae60"),
            (150, 200, "경계", "#f39c12"),  # 노트북 원본의 경계 갭 수정(상한=다음 구간 하한)
            (200, 500, "높음", "#e67e22"),  # 노트북 원본의 경계 갭 수정(상한=다음 구간 하한)
            (500, 9999, "매우 높음", "#e74c3c"),
        ],
    },
    "ast": {
        "unit": "U/L",
        "target": "40 이하",
        "stages": [(0, 41, "정상", "#27ae60"), (41, 999, "위험", "#e74c3c")],
    },
    "alt": {
        "unit": "U/L",
        "target": "40 이하",
        "stages": [(0, 41, "정상", "#27ae60"), (41, 999, "위험", "#e74c3c")],
    },
    "sitting_hours": {
        "unit": "시간",
        "target": "6시간 미만",
        "stages": [
            (0, 6, "적정", "#27ae60"),
            (6, 8, "주의", "#f39c12"),
            (8, 999, "위험", "#e74c3c"),
        ],
    },
    "walking_days": {
        "unit": "일/주",
        "target": "주 5일 이상",
        "stages": [
            (5, 99, "양호", "#27ae60"),
            (3, 5, "부족", "#f39c12"),
            (0, 3, "매우 부족", "#e74c3c"),
        ],
    },
    "moderate_days": {
        "unit": "일/주",
        "target": "주 5일 이상",
        "stages": [
            (5, 99, "양호", "#27ae60"),
            (3, 5, "부족", "#f39c12"),
            (0, 3, "매우 부족", "#e74c3c"),
        ],
    },
    "vigorous_days": {
        "unit": "일/주",
        "target": "주 3일 이상",
        "stages": [
            (3, 99, "양호", "#27ae60"),
            (1, 3, "부족", "#f39c12"),
            (0, 1, "매우 부족", "#e74c3c"),
        ],
    },
    "smoking_current": {
        "unit": "",
        "target": "비흡연",
        "stages": [(0, 0.5, "비흡연", "#27ae60"), (0.5, 2, "흡연", "#e74c3c")],
    },
}

# 또래 연령대 분류 — lifestyle_score 분포 조회 시 연령대 단위
# Task 4: train_stats 연령대별 또래 lifestyle 분포 동결 시 사용
PEER_AGE_DECADES: list[int] = [40, 50, 60, 70, 80]
