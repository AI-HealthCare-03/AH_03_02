"""학습된 predictor로 pipeline.run_inference end-to-end 검증 (수동 실행).

AutoGluon predictor 로드가 필요하므로 학습 전용 3.11 venv에서 실행한다.
    CKD_DATA_DIR=<260520> .venv-train/bin/python scripts/verify_ckd_predict.py

mapping → preprocess(ldl·대치·eGFR) → features(winsor·log·파생) → predict 전체가
실제 predictor로 끝까지 도는지, app_group이 임상 규칙대로 배정되는지 확인한다.
"""

from __future__ import annotations

import json
from datetime import date

import pandas as pd

from src.ckd import config, pipeline, predict, train_stats

REF_DATE = date(2024, 6, 1)

BASE = {
    "gender": "MALE",
    "birthday": date(1970, 6, 1),
    "systolic_bp": 118,
    "diastolic_bp": 76,
    "fasting_glucose": 92,
    "total_cholesterol": 185,
    "hdl_cholesterol": 55,
    "triglycerides": 110,
    "creatinine": 0.9,
    "height": 172,
    "weight": 70,
    "bmi": 23.7,
    "waist_circumference": 84,
    "ast": 24,
    "alt": 22,
    "hemoglobin": 15.1,
    "urine_protein_qual": 0,
    "urine_glucose": 0,
    "smoking_status": "NEVER",
    "drinking_frequency": "MONTHLY",
    "marital_status": "MARRIED",
    "vigorous_exercise_days": 3,
    "moderate_exercise_days": 2,
    "walking_days_per_week": 5,
    "sitting_hours_per_day": 7.0,
    "family_history_diabetes": False,
    "family_history_hypertension": False,
    "family_history_heart_disease": False,
    "family_history_dyslipidemia": False,
    "family_history_stroke": False,
    "htn_diagnosed": False,
    "dm_diagnosed": False,
    "dyslipidemia_diagnosed": False,
}

CASES = {
    "건강한 50대 남성 (정상)": BASE,
    "고혈압·당뇨 진단 (임상위험)": {
        **BASE,
        "systolic_bp": 148,
        "fasting_glucose": 138,
        "htn_diagnosed": True,
        "dm_diagnosed": True,
    },
    "신기능 저하 (creatinine 2.5 → eGFR<60)": {**BASE, "creatinine": 2.5},
    # A그룹 테스트 페르소나 — 코랩 검증 dict(모델 raw 피처)를 서비스 입력 형식으로 변환.
    # 파생변수(bp_status·anemia·pulse_pressure·*_log·*_ratio 등)는 features.py가 자동 계산하므로 원자료만 채운다.
    "A그룹 — 김철수(58·남·고혈압·당뇨·가족력)": {
        **BASE,
        "birthday": date(1966, 6, 1),  # 58세 (REF_DATE 2024-06-01 기준)
        # 검진(HealthCheck) — 복부비만·고혈압·고혈당·신기능 저하
        "systolic_bp": 150,
        "diastolic_bp": 92,
        "fasting_glucose": 145,
        "creatinine": 1.6,  # → eGFR<60 → app_group A(G1)
        "total_cholesterol": 210,
        "hdl_cholesterol": 42,
        "ldl_cholesterol": 135,  # 검진값 존재 → Friedewald 미추정(ldl_is_estimated=0)
        "triglycerides": 210,
        "ast": 30,
        "alt": 35,
        "hemoglobin": 13.5,
        "urine_protein_qual": 1,  # 요단백 양성
        "urine_glucose": 1,  # 요당 양성
        "weight": 81,
        "bmi": 27.4,
        "waist_circumference": 98,  # 복부비만(남 ≥90)
        # 문진(LifestyleSurvey) — 진단력·가족력·생활습관
        "htn_diagnosed": True,  # 본인 고혈압 진단
        "dm_diagnosed": True,  # 본인 당뇨 진단
        "family_history_diabetes": True,  # 가족력 당뇨
        "family_history_hypertension": True,  # 가족력 고혈압
        "smoking_status": "CURRENT",  # 현재 흡연
        "drinking_frequency": "W2_3",  # 주 2~3회 (음주 6단계, 명세 §3.1)
        "vigorous_exercise_days": 0,
        "moderate_exercise_days": 1,
        "walking_days_per_week": 2,
        "sitting_hours_per_day": 9.0,  # 좌식 9시간
    },
}


def main() -> None:
    p1, _p2 = predict.load_predictors()
    stats = train_stats.extract_stats(pd.read_csv(config.TRAIN_CSV))
    thr = json.loads(config.THRESHOLD_PATH.read_text(encoding="utf-8"))["recall_threshold"]
    print(f"threshold(recall) = {thr:.4f}\n")

    for name, data in CASES.items():
        out = pipeline.run_inference(data, REF_DATE, p1, thr, stats)
        print(f"[{name}]")
        print(
            f"  app_group={out['app_group']}  risk={out['ckd_risk_score']:.4f}  "
            f"stage={out['ckd_stage']}  eGFR={out['egfr_estimated']:.1f}"
        )


if __name__ == "__main__":
    main()
