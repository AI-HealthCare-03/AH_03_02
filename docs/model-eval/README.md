# CKD 예측 모델 성능 평가 — REQ 평가 3-1

**평가 항목**: 지속적인 모델 성능 검증 및 결과 분석 (학습·검증 데이터 분리 + 2개 이상 지표 + 실험 비교)
**결과**: ✅ **모델1 ROC-AUC 0.902 / 모델2 0.883** — 목표(AUROC ≥ 0.80, REQ-ML)를 두 모델 모두 초과
**측정 일자**: 2026-06-18 · **test set**: `test_final_v2.csv` (학습 미사용 hold-out, 8,964건)

> 원본 측정 결과는 [`result.json`](result.json)에 저장돼 있으며 `scripts/eval_ckd_models.py`로 재현 가능합니다.

---

## 1. 데이터 분할

KNHANES(국민건강영양조사) 공개 데이터를 **train / val / test 3분할**로 가공(`*_final_v2.csv`).
- **train**: 모델 학습 (AutoGluon `best_quality`, 5-fold bagging)
- **val**: 운영 임계값(threshold) 산출 — Youden / Recall≥0.88
- **test**: 본 평가에만 사용 (학습·임계값 산출에 일절 미사용 → 데이터 누수 없음)

test set: **8,964건 중 CKD 양성 357건 (양성률 3.98%)** — 임상적으로 자연스러운 **불균형** 분포.

> creatinine·eGFR은 그룹 배정(`app_group`)에만 쓰고 **모델 입력에서 제외**(데이터 누수 방지, `config.GROUP_COLS`).

## 2. 모델 구성

| 모델 | 용도 | 피처 수 | 학습 지표 |
|---|---|---:|---|
| **모델1** | 임상 마커가 풍부한 사용자 (검진 수치 완비) | 42 | ROC-AUC |
| **모델2** | 검진 정보가 적은 사용자 (생활습관 중심, 혈압·혈당·creatinine 없음) | 24 | Average Precision |

두 모델 모두 AutoGluon TabularPredictor 앙상블(`best_quality`).

## 3. 핵심 성능 지표 (test set)

불균형 데이터이므로 ROC-AUC와 함께 **PR-AUC**(소수 양성 탐지력)·**Brier**(확률 보정)를 핵심으로 본다.

| 지표 | 모델1 (임상 42) | 모델2 (생활습관 24) | 해석 |
|---|---:|---:|---|
| **ROC-AUC** | **0.902** | **0.883** | 목표 0.80 초과. 모델1이 임상 마커 덕에 우위 |
| **PR-AUC** | 0.351 | 0.295 | 양성률 4% 기준선(0.04) 대비 8~9배 — 불균형에서 양호 |
| **Brier score** | 0.031 | 0.033 | 0에 가까울수록 보정 우수 (낮을수록 좋음) |

## 4. 운영 임계값별 분류 지표 (val 기준 임계값 → test 측정)

본 서비스는 **선별(screening) 도구**다 — "의사에게 가야 할 사람을 놓치지 않는 것"이 최우선이므로, **재현율(recall)을 높이고 정밀도(precision)는 낮게** 운영한다(거짓양성=불필요한 정밀검사 권유는 허용, 거짓음성=놓침은 최소화).

### 모델1
| 임계값 정책 | threshold | Recall | Precision | F1 | 놓친 양성(FN) |
|---|---:|---:|---:|---:|---:|
| Youden | 0.061 | 0.840 | 0.158 | 0.266 | 57 / 357 |
| **Recall≥0.88** | 0.055 | **0.863** | 0.150 | 0.256 | **49 / 357** |

### 모델2
| 임계값 정책 | threshold | Recall | Precision | F1 | 놓친 양성(FN) |
|---|---:|---:|---:|---:|---:|
| Youden | 0.052 | 0.821 | 0.142 | 0.242 | 64 / 357 |
| **Recall≥0.88** | 0.040 | **0.871** | 0.125 | 0.218 | 46 / 357 |

> **낮은 precision은 결함이 아니라 정책**이다. 양성률 4%의 선별 문제에서 recall 0.86은 실제 CKD 위험군의 86%를 걸러낸다는 의미이며, 거짓양성은 "정밀검사를 한 번 더 권유"하는 비용이라 임상적으로 수용 가능하다.

## 5. 실험 비교 결론

- **모델1 > 모델2** (ROC-AUC 0.902 vs 0.883, 모든 지표에서 모델1 우위) — 임상 마커(혈압·혈당·간효소 등)가 예측력을 끌어올림.
- **모델2도 0.88로 우수** — 검진 정보가 부족한 사용자에게 생활습관·기본 신체계측만으로 fallback 예측을 제공.
- 두 모델 모두 **목표 AUROC 0.80을 명확히 초과**, 확률 보정(Brier 0.03)도 양호.

## 6. 평가 3-1 충족 근거

| 5점 기준 | 충족 |
|---|---|
| 학습·검증 데이터 분리 | ✅ train/val/test 3분할, test는 학습·임계값 산출 미사용 |
| 2개 이상 성능 지표 | ✅ ROC-AUC · PR-AUC · Brier + recall/precision/F1 |
| 실험 비교 결과 제시 | ✅ 모델1 vs 모델2 정량 비교 + 임계값 정책 2종 비교 |

## 7. 재현성 검증 — 동일 입력 결과 편차 (평가 3-3)

산출물(predictor·threshold·train_stats) 동결 + 전처리 순수함수 + 학습 시드 고정(`src/ckd/train.py` `SEED=42`)으로 **동일 입력은 항상 동일 출력**을 낸다. test 샘플 200건을 각 **20회 반복 예측**해 정량 검증했다.

| 모델 | 반복 | 샘플 | 최대 표준편차 | 결정론 |
|---|---:|---:|---:|:---:|
| 모델1 (임상 42) | 20회 | 200건 | **0.0** | ✅ |
| 모델2 (생활습관 24) | 20회 | 200건 | **0.0** | ✅ |

- 모든 샘플의 반복 예측 표준편차가 **0** → 완전 결정론(편차 없음)
- 검증 스크립트: `scripts/check_determinism.py` (산출물 [`determinism.json`](determinism.json))
- RAG 챗봇(LLM)은 `temperature=0`으로 편차 최소화(ADR-0005)하나 bit-identical 보장 범위는 아님

## 8. 재현 방법

```bash
# AutoGluon은 Python 3.11 필요 → 학습 전용 venv 사용
CKD_DATA_DIR=<train/val/test_final_v2.csv 디렉토리> \
  .venv-train/bin/python scripts/eval_ckd_models.py        # 성능 지표 + result.json
  .venv-train/bin/python scripts/check_determinism.py      # 재현성 + determinism.json
```
