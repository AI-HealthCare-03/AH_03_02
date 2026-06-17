# ADR-0008: CKD 예측 모델 학습 — AutoGluon

**Date**: 2026-06-18
**Status**: ✅ Accepted

## Context

CKD 위험을 예측하는 이진 분류 모델이 필요하다. 데이터·제약:

- KNHANES 정형 표 데이터, **양성률 약 4%의 불균형**
- 부트캠프 기간 내 **앙상블·하이퍼파라미터 튜닝·보정**을 빠르게 확보
- 검진 정보가 풍부한 사용자(모델1, 42피처)와 적은 사용자(모델2, 24피처) **2개 모델**
- 학습은 오프라인 1회, 서비스는 산출물(predictor)만 로드해 추론

## Decision

**AutoGluon `TabularPredictor`**(`best_quality` 프리셋, 5-fold bagging, stacking) 채택. 학습 전용 Python 3.11 venv에서 실행, 산출물(predictor 디렉토리)을 서비스가 로드.

## Alternatives Considered

| 후보 | 장점 | 단점 | 기각 사유 |
|---|---|---|---|
| 수동 LightGBM/XGBoost | 완전 제어, 가벼움 | 앙상블·튜닝·교정을 직접 구현 → 시간 ↑ | 기간 내 품질 확보 비용 |
| scikit-learn 파이프라인 | 표준·투명 | AutoML 기능 없음(튜닝·스태킹 수동) | 자동화 부족 |
| H2O AutoML | 강력한 AutoML | JVM 의존, 배포 무거움 | 파이썬 스택과 이질적 |
| **AutoGluon** ⭐ | 자동 앙상블·스태킹·보정, 표 데이터 SOTA급, 적은 코드로 고품질 | Python 3.11 고정(3.13 미지원), 추론 의존성 무거움, 블랙박스 | — (선택) |

## Consequences

### 좋은 점
- 자동 앙상블·스태킹·확률 보정으로 **test ROC-AUC 0.90(모델1)·0.88(모델2)** 달성 (→ `docs/model-eval`)
- 적은 코드로 두 모델(임상/생활습관) 일관 학습
- 내부 LightGBM booster를 꺼내 **TreeSHAP 설명**(리포트) 재사용

### 트레이드오프
- AutoGluon이 Python 3.11까지만 지원 → 학습 venv를 3.11로 고정(`.venv-train`)
- predictor 의존성이 무거워 추론 컨테이너(ai-worker) 이미지 크기 ↑
- AutoML 특성상 모델 내부가 블랙박스 → SHAP로 설명가능성 보완

### 운영 영향
- 학습: `CKD_DATA_DIR=<...> .venv-train/bin/python -m src.ckd.train`
- 산출물(predictor·threshold·train_stats)은 git 제외, ai-worker에 읽기 전용 마운트
- 성능 검증: `scripts/eval_ckd_models.py`(test set 지표·모델 비교, ADR-연계)
