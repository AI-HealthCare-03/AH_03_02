# 검사 수치 기록장 — 수직 슬라이스 설계 (기록 기능 slice 6)

- 작성일: 2026-06-11
- 브랜치: `feat/record-lab`
- 출처: 콩팥 챌린지 기록 기능 기획서 §2-7 "검사 수치 기록장" (+ §5 archive.lab_records)
- 범위: **프론트(전용 페이지)+백엔드(record 레이어 확장)**. 기존 record 패턴 + 신규 지표 카탈로그/커스텀 항목.

---

## 1. 목표
트랙별 검사 지표를 **검사일별로 입력**하고, 지표별 **최신값+이전 대비 증감**·**최근 5회 추세 꺾은선**·**참고범위 표시선**(참고용, 진단 아님)을 보여주는 **전용 페이지**. 사용자가 추적 지표를 **추가/제거**할 수 있고, 검사 기록 시 **MONITORING 카테고리 챌린지 자동 체크인**. CKD 예측 입력(HealthCheck)과 완전 분리.

## 2. 아키텍처
record 레이어 확장 + 전용 프론트 페이지.
- **`lab_reference.py`** (신규, SSOT): 지표 카탈로그(키·라벨·단위·소수자리·참고범위·성별의존·트랙 기본세트) + 참고범위 성별 해석 + 트랙 기본 지표 → **순수함수**, L1.
- 모델 2종: `LabRecord`(검사일별 값 dict, upsert), `UserLabMetrics`(사용자 활성 지표 — 커스텀).
- repository 2종 / DTO / `LabService` / router `/records/lab` / 프론트 전용 `LabRecordPage` + 라우트 + 진입 링크.
- **MONITORING 자동 체크인**: `LabService`는 `RecordService`와 **분리된 신규 서비스**이므로 RecordService의 private 메서드를 직접 호출하지 않는다(RecordService 미수정 → 기존 기능 회귀 0). 대신 LabService가 `ChallengeService`를 주입받아 **동일 패턴의 자체 MONITORING 체크인 메서드**(`_maybe_auto_checkin_monitoring`, try/except graceful, ACTIVE+이미체크인 방어)를 갖는다(~12줄, RecordService의 헬퍼와 동일 로직).
- **HealthCheck(예측·SHAP·RAG 파이프라인)는 일절 건드리지 않는다. RecordService도 미수정.**

## 3. 데이터 모델 (`app/models/record.py`에 추가)
```python
class LabRecord(models.Model):
    """검사 1회(날짜) = 1행. 검사일별 지표값 dict, 수정 가능(upsert)."""
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="lab_records")
    measured_date = fields.DateField(description="검사일")
    values = fields.JSONField(description="입력한 지표값 {metric_key: float}")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "lab_records"
        unique_together = [("user", "measured_date")]
        ordering = ["-measured_date"]


class UserLabMetrics(models.Model):
    """사용자가 추적할 지표 키 목록(커스텀). 없으면 트랙 기본 지표 사용."""
    id = fields.BigIntField(primary_key=True)
    user = fields.OneToOneField("models.User", related_name="lab_metrics")
    metric_keys = fields.JSONField(description="활성 지표 키 list[str]")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_lab_metrics"
```
`aerich migrate`.

## 4. 지표 카탈로그 (`lab_reference.py` — 16종)
참고범위는 기획서 §2-7 "정상 범위 참고값" 표 근거. 범위는 `(low, high)` 형태이며 한쪽이 None이면 무한(상한/하한만). 성별의존(Hb·creatinine)은 `(low, high)`를 성별별로 보유.

| key | 라벨 | 단위 | 소수 | 참고범위 | 트랙 기본 |
|---|---|---|---|---|---|
| potassium | 칼륨(K) | mEq/L | 1 | 3.5~5.0 | DIALYSIS |
| phosphorus | 인(P) | mg/dL | 1 | 2.5~4.5 | DIALYSIS |
| hemoglobin | 헤모글로빈 | g/dL | 1 | 남 13.5~17.5 / 여 12.0~16.0 | DIALYSIS |
| dialysis_weight_pre | 투석 전 체중 | kg | 1 | — | DIALYSIS |
| dialysis_weight_post | 투석 후 체중 | kg | 1 | — | DIALYSIS |
| egfr | eGFR | mL/min/1.73㎡ | 0 | ≥60 (low=60) | CKD |
| creatinine | 크레아티닌 | mg/dL | 2 | 남 0.7~1.2 / 여 0.5~1.0 | CKD |
| systolic_bp | 수축기혈압 | mmHg | 0 | <130 (high=130) | CKD·INTENSIVE·DAILY·WELLNESS |
| diastolic_bp | 이완기혈압 | mmHg | 0 | <80 (high=80) | CKD·INTENSIVE·DAILY·WELLNESS |
| proteinuria | 단백뇨 | mg/dL | 1 | — | CKD |
| fasting_glucose | 공복혈당 | mg/dL | 0 | 70~100 | INTENSIVE·DAILY |
| postprandial_glucose | 식후혈당 | mg/dL | 0 | — | INTENSIVE·DAILY |
| hba1c | HbA1c | % | 1 | — | INTENSIVE·DAILY |
| ldl | LDL | mg/dL | 0 | <100 (high=100) | INTENSIVE·DAILY·WELLNESS |
| hdl | HDL | mg/dL | 0 | — | INTENSIVE·DAILY·WELLNESS |
| weight | 체중 | kg | 1 | — | WELLNESS |

**트랙 기본 지표 세트**(`default_metric_keys`):
- DIALYSIS: potassium, phosphorus, hemoglobin, dialysis_weight_pre, dialysis_weight_post
- CKD: egfr, creatinine, systolic_bp, diastolic_bp, proteinuria
- INTENSIVE: systolic_bp, diastolic_bp, fasting_glucose, postprandial_glucose, hba1c, ldl, hdl
- DAILY: systolic_bp, diastolic_bp, fasting_glucose, postprandial_glucose, hba1c, ldl, hdl
- WELLNESS: systolic_bp, diastolic_bp, weight, ldl, hdl

**순수 함수**:
- `all_metric_keys() -> list[str]` — 카탈로그 16 키.
- `metric_def(key) -> dict` — {key, label, unit, decimals}.
- `default_metric_keys(track: ChallengeTrack) -> list[str]`.
- `resolve_range(key, gender) -> tuple[float | None, float | None] | None` — 참고범위(성별 반영), 없으면 None.
- `is_valid_metric(key) -> bool`.

## 5. 백엔드
### 5.1 LabRecordRepository (record_repository.py)
- `upsert(user_id, measured_date, values: dict) -> LabRecord` (날짜별 1행 수정)
- `get_by_date(user_id, measured_date) -> LabRecord | None`
- `recent(user_id, limit: int) -> list[LabRecord]` (measured_date 내림차순 limit — 추세용)
- `delete_by_date(user_id, measured_date) -> bool`

### 5.2 UserLabMetricsRepository (record_repository.py)
- `get(user_id) -> UserLabMetrics | None`
- `upsert(user_id, metric_keys: list[str]) -> UserLabMetrics`

### 5.3 LabService (신규 `app/services/lab.py` — record.py 비대화 방지)
- `_active_keys(user_id) -> list[str]` — UserLabMetrics 있으면 그 키(카탈로그 교집합), 없으면 `default_metric_keys(track)`. 트랙은 UserChallengeProfile, 없으면 DAILY.
- `get_metrics(user_id) -> MetricsResponse` — 활성 키 + 각 메타(label·unit·decimals·range[성별해석]) + 전체 카탈로그(관리 UI용).
- `get_overview(user_id) -> OverviewResponse` — 활성 지표별 {key, label, unit, latest, prev, delta, range, points: 최근5회 [(date,value)]}. 최근 5개 LabRecord에서 각 지표 추출(값 있는 것만).
- `save_record(user_id, measured_date, values) -> SaveResponse` — 활성 지표 키로 필터한 값만 upsert → `_maybe_auto_checkin_monitoring`.
- `set_metrics(user_id, metric_keys) -> MetricsResponse` — 카탈로그 검증(`is_valid_metric`) 후 upsert. 검증 실패 422.
- `get_record(user_id, measured_date)` / `delete_record(user_id, measured_date)`.
- `_maybe_auto_checkin_monitoring(user_id, today)` — ACTIVE MONITORING 챌린지 조회 → 오늘 미체크인이면 `ChallengeService.checkin` → AutoCheckinResult. 전체 try/except graceful(체크인 실패해도 검사 기록 성공 유지). 체크인 today는 `date.today()`(검사일 measured_date와 무관 — "오늘 기록 행위"에 대한 체크인). `AutoCheckinResult`는 `app.dtos.record`에서 재사용 import.
- `__init__(self)`: `self._lab = LabRecordRepository()`, `self._user_metrics = UserLabMetricsRepository()`, `self._challenge = ChallengeService()`.
- gender는 `User.get(id=user_id)`에서 조회.

### 5.4 DTO (`app/dtos/lab.py` 신규)
- `MetricDef { key, label, unit, decimals, range_low: float|None, range_high: float|None }`
- `MetricsResponse { active_keys: list[str], active: list[MetricDef], catalog: list[MetricDef] }`
- `SetMetricsRequest { metric_keys: list[str] (min_length 0 허용) }`
- `SaveLabRequest { measured_date: date, values: dict[str, float] }` (값은 ge=0; 키 검증은 서비스)
- `LabPoint { date: date, value: float }`
- `MetricOverview { key, label, unit, decimals, latest: float|None, prev: float|None, delta: float|None, range_low, range_high, points: list[LabPoint] }`
- `OverviewResponse { metrics: list[MetricOverview], disclaimer: str }`
- `SaveLabResponse { measured_date, saved_keys: list[str], auto_checkin: AutoCheckinResult }`
- `LabRecordResponse { measured_date: date|None, values: dict[str, float], has_record: bool }`

### 5.5 Router (`app/apis/v1/lab_routers.py` 신규, prefix `/records/lab`)
| 메서드 | 경로 | 응답 |
|---|---|---|
| GET | `/records/lab/metrics` | MetricsResponse |
| PUT | `/records/lab/metrics` | MetricsResponse |
| GET | `/records/lab/overview` | OverviewResponse |
| GET | `/records/lab?date=YYYY-MM-DD` | LabRecordResponse |
| PUT | `/records/lab` | SaveLabResponse |
| DELETE | `/records/lab?date=YYYY-MM-DD` | LabRecordResponse |
- `Depends(get_request_user)` 소유권. 라우터는 `app/main.py`(또는 v1 라우터 집계 지점)에 등록.

## 6. 프론트 — 전용 페이지 `LabRecordPage` + 라우트
- `api/lab.ts` 신규(labApi: getMetrics/setMetrics/getOverview/getRecord/saveRecord/deleteRecord).
- 라우트 추가(plan 단계에서 App 라우팅 구조 확인 후 경로 확정, 예 `/records/lab`) + 진입 링크(챌린지 메인 또는 네비).
- `LabRecordPage.tsx`:
  - **검사 입력 폼**: 검사일(`<input type="date">`) + 활성 지표별 숫자 입력 → 저장(빈 칸 제외).
  - **지표 카드 그리드**: 지표별 최신값 + 증감 뱃지(범위 밖이면 색 강조) + **최근 5회 Recharts `LineChart`** + **참고범위 `ReferenceArea`/`ReferenceLine`**(성별 반영). 데이터 없으면 안내.
  - **지표 관리(추가/제거)**: 카탈로그 토글 → `PUT /metrics`로 활성 지표 갱신.
  - 저장 시 `["record","lab"]`·`["challenges"]`·`["points","balance"]` invalidate + MONITORING 자동체크인 반영.
  - 상단에 **"참고범위는 표시용이며 의료 진단이 아닙니다"** 면책 명시.
- `recharts ^3.8.1` 설치됨.

## 7. 에러·면책
- `values`의 수치는 ge=0(음수 422). 비정상적으로 큰 값은 지표별 상한 없이 허용(자기기록). 저장 시 **활성 지표 외 키는 무시**.
- `set_metrics`에서 카탈로그에 없는 키 → 422.
- 자동체크인 실패 → 기록 200/201 유지(독립 try/except).
- 참고범위는 **표시 전용** — UI에 의료 면책 문구 명시.

## 8. 범위 외
- **CSV/PDF 내보내기** — 후속 슬라이스(기획서 §2-7 내보내기).
- BMI 자동 계산, OCR 연동(기존 OCR은 HealthCheck 전용) — 범위 외.
- 지표별 알림·단위 변환 — 범위 외.

## 9. 테스트
- **L1**(lab_reference): `default_metric_keys`(5 트랙 세트), `resolve_range`(Hb·creatinine 성별 / eGFR 하한 / LDL·BP 상한 / 범위없음 None), `is_valid_metric`.
- **L2**: LabRecord upsert(같은 날 수정), `get_overview`(증감·최근5회·범위), `_active_keys`(설정 없으면 트랙 기본·설정 있으면 그 키), `set_metrics`(검증·추가/제거), MONITORING 자동체크인·graceful.
- **L3**: API metrics(GET/PUT)·overview·save·get·delete, 인증·소유권, 잘못된 키 PUT 422, 음수 값 422.
- ⚠️ 로컬 `pytest app` 금지(운영DB drop) — CI 위임. 로컬 ruff + `python -c` + docker E2E.

## 10. 구현 순서 (writing-plans 입력)
1. `lab_reference.py` 카탈로그 + 함수(all/metric_def/default_metric_keys/resolve_range/is_valid_metric) (+L1)
2. LabRecord·UserLabMetrics 모델 + `aerich migrate`
3. LabRecordRepository + UserLabMetricsRepository
4. lab DTO (`app/dtos/lab.py`)
5. LabService (`app/services/lab.py`) — MONITORING 자동체크인 재사용
6. lab_routers + 등록 + L2/L3
7. 프론트 api/lab.ts + LabRecordPage(입력·지표카드·추세·참고범위) + 라우트/진입
8. 지표 관리(추가/제거) UI 통합
9. docker E2E(저장·추세·범위·활성지표 변경·자동체크인) + PR
