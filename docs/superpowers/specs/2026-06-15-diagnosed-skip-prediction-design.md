# 모듈 ① — CKD 진단자 예측·리포트 스킵 (백엔드)

> 작성일: 2026-06-15 · 브랜치: `feat/diagnosed-skip-prediction`
> 상위 그림: "서비스를 CKD 진단자 / 비진단자로 최상위에서 가르고, 대시보드·챌린지까지 일관되게 구별한다"의 첫 모듈.

## 1. 배경 / 정책

서비스 본질은 **선별(screening)** 이다. 아직 진단받지 않은 사용자를 관리해 의사에게 갈 사람을 찾는 것이 핵심이며, **이미 CKD 진단을 받은 사용자는 의료영역**이라 서비스가 위험도를 예측하거나 리포트로 개입하지 않는다.

따라서 진단자에게는 다음을 **생성하지 않는다**:
- ML CKD 위험도 예측 (`ckd_risk_score`)
- SHAP 설명 (`shap_model1`, `shap_model2`)
- RAG AI 리포트 가이드 (`ai_guide`)

진단자 판별 = `LifestyleSurvey.ckd_diagnosed == True`. 그 결과로 검진 시점에 `HealthCheck.app_group`이 `CKD`(비투석) 또는 `DIALYSIS`(투석·이식)로 동기 확정된다. `app_group ∈ {CKD, DIALYSIS}` 가 곧 "진단자"의 신호다.

### 전체 그림(맥락, 본 모듈 범위 아님)

| 기능 축 | 비진단자(관리대상) | 진단자(의료영역) |
|---------|------------------|-----------------|
| ML 위험도 예측 | ✅ | ❌ (본 모듈) |
| 리포트 `/llm-guide` | ✅ SHAP+AI가이드 | ❌ (본 모듈) |
| 대시보드 | eGFR·위험도·경고 | 관리 중심 (모듈 ②) |
| 챌린지 | INTENSIVE/DAILY/WELLNESS | CKD/DIALYSIS 전용 화면 (모듈 ③) |

## 2. 현재 흐름의 갭 (전부 진단자 분기 없음)

```
검진 저장  app/services/health_check.py:188  ckd_diagnosed 조회 → app_group=CKD/DIALYSIS 동기 확정 ✅
              ↓ (라인 225, 조건 없이 발행) ❌
        ckd_publisher.publish_ckd_job  →  redis ckd_jobs  →  ai_worker
              ↓
        run_inference (risk + SHAP)  →  db.update_prediction (app_group만 보호, risk/shap는 진단자도 갱신) ❌
              ↓
        _spawn_guide_task (ckd_task.py:133, 조건 없이)  →  ai_guide 저장 ❌

리포트 조회  app/services/health_check.py:698 get_report  →  진단자도 shap/ai_guide 전체 반환 ❌
```

확인된 코드 위치:
- 발행: `app/services/health_check.py:225-238` (`create_health_check` 내, 조건 없이 `publish_ckd_job`)
- 예측 저장: `ai_worker/core/db.py:34-66` (`update_prediction`, `app_group`만 CASE 보호)
- 가이드: `ai_worker/tasks/ckd_task.py:133` (`_spawn_guide_task`, 무조건)
- 리포트: `app/services/health_check.py:698-741` (`get_report`)

## 3. 설계

### 3-1. 발행 가드 (핵심)

`create_health_check`는 **이미 `ckd_diagnosed`를 조회**하고 있다(`health_check.py:188-190`). 그 값으로 발행을 분기한다.

- `ckd_diagnosed == True` → `publish_ckd_job` **스킵** + `logger.info`("진단자 — 예측 job 미발행 hc=…")
- `ckd_diagnosed == False` → 기존대로 발행

결과: 진단자의 `HealthCheck`는 `ckd_risk_score`·`shap_model1`·`shap_model2`·`ai_guide`가 NULL로 남고, `app_group`은 동기 `CKD`/`DIALYSIS`로 유지된다. **ai_worker는 수정하지 않는다** (job 자체가 발행되지 않으므로 예측·SHAP·가이드가 전부 자동 스킵).

방안 비교(채택=A): A 발행 스킵(단일 지점·SSOT·ai_worker 무수정·가이드까지 자동 스킵) / B 소비 스킵(발행 후 버림·cross-layer) / C `update_prediction` CASE 확장(가이드 안 막힘). → **A**.

### 3-2. 리포트 조회 가드 (① → ② 인터페이스 계약)

`get_report`(`health_check.py:698`)는 이미 `hc`를 로드한다. 진단자 판별을 추가한다.

- 판별: `hc.app_group ∈ {CKD, DIALYSIS}` (검진 시점 동기 확정값 — 추가 조회 불필요)
- `ReportResponse.report_meta`에 플래그 추가: **`report_available: bool`** (진단자면 `false`)
- `risk`/`shap`/`ai_guide`는 빈값 그대로 반환 (404 아님 — graceful). 프론트가 깨지지 않게.
- 모듈 ②(대시보드·리포트 프론트)가 이 플래그로 "진단자는 리포트 비대상 → 주치의 지시" 안내를 띄운다.

`report_meta`의 정확한 위치/기존 필드는 구현 시 `ReportResponse`·`report_meta` DTO를 확인해 맞춘다. 기존 키는 불변, 신규 키만 추가(하위호환).

### 3-3. 판별 기준 SSOT

- **발행 가드** = `ckd_diagnosed`(설문 최신값, `create_health_check`가 이미 조회).
- **리포트 가드** = `hc.app_group ∈ {CKD, DIALYSIS}`(검진 시점 확정값).
- 두 값은 진단자 검진 시 일치한다(`_assign_app_group`가 `ckd_diagnosed`로 CKD/DIALYSIS 배정). 각 지점에서 이미 로드된 값을 쓰므로 추가 쿼리 없음.

## 4. 테스트

- **발행 스킵 단위테스트**: `ckd_publisher.publish_ckd_job`을 mock → 진단자(`ckd_diagnosed=True`) 검진 저장 시 **호출 안 됨**, 비진단자 시 **호출됨**. (`app/services/test_*.py` 위치 확인 — `app/tests`와 `app/services/test_*.py` 둘 다 점검)
- **리포트 플래그 테스트**: `get_report` — 진단자(`app_group=CKD/DIALYSIS`)→`report_available=false`, 비진단자→`true`.
- **회귀**: health_check 관련 기존 테스트 통과. DTO 키 추가가 기존 응답 검증을 깨지 않는지.
- 로컬 `pytest app` **금지**(conftest TEST_DB_URL이 운영 postgres를 drop하는 사고 이력) → 로컬은 `ruff` lint만, pytest는 CI(격리)에 위임. 컨테이너 import 검증은 `uv run python -c`로.

## 5. 검증 (E2E, docker)

- ai_worker 무수정 → **rebuild 불필요**, `fastapi`는 app 볼륨 마운트라 `docker compose restart fastapi`로 충분.
- 진단자 계정: 검진 저장 → `ckd_jobs` 미발행(로그 확인) → `health_checks` risk/shap/ai_guide NULL, `app_group=CKD/DIALYSIS` → `get_report` `report_available=false`.
- 비진단자 계정: 검진 저장 → 정상 발행·예측·SHAP·가이드 → `get_report` `report_available=true`.

## 6. 범위 밖

- 프론트 대시보드·리포트 화면 변경 → **모듈 ②**.
- 진단자 챌린지 전용 화면(서브탭) → **모듈 ③** (별도 설계 거의 완료: 별도 페이지+공유 훅+상단 서브탭).
- 기존 진단자 데이터 백필(과거 생성된 risk/shap) → 하지 않음. 새 검진부터 적용, 시연 계정은 재생성.
- `update_prediction`의 CASE 가드(app_group 보호)는 그대로 둔다(혹시 모를 비정상 경로 안전판).

## 7. 파일 변경 요약

| 종류 | 파일 | 변경 |
|------|------|------|
| 수정 | `app/services/health_check.py` | `create_health_check` 발행 가드(진단자 스킵) + `get_report` `report_available` 플래그 |
| 수정 | `app/dtos/*` (report_meta DTO) | `report_available: bool` 신규 필드(하위호환) |
| 신규/수정 | `app/services/test_*.py` 또는 `app/tests/*` | 발행 스킵·리포트 플래그 테스트 |
| 무수정 | `ai_worker/**` | 변경 없음 |
