# 병원 진료일 캘린더 — 수직 슬라이스 설계 (기록 기능 slice 7, 마지막)

- 작성일: 2026-06-11
- 브랜치: `feat/record-appointments`
- 출처: 콩팥 챌린지 기록 기능 기획서 §2-6 "병원 진료일 캘린더" (+ §5 archive.appointments)
- 범위: **프론트(전용 페이지)+백엔드(record 레이어 확장)**. 검사 수치 기록장과 동일 골격(전용 페이지·별도 서비스), 게이미피케이션·예측 무관.

---

## 1. 목표
정기 진료·투석·검사 예약을 날짜별로 **등록·수정·삭제**하고, **월별 캘린더(일정 있는 날 도트)**·**다음 진료 D-day 카운트다운**·**예정 일정 목록(오늘↑ 최대 5건)**·**지난 일정 아카이브**를 전용 페이지로 제공한다. 시간예약 푸시 알림은 스케줄러 인프라가 없어 **연기**하고, 앱 접속 시 **D-day·예정 목록·다가오는 일정 배너**로 놓침을 방지한다. 챌린지 자동 체크인·HealthCheck(예측)·RecordService 모두 **미수정**.

## 2. 아키텍처
record 레이어 확장 + 전용 프론트 페이지.
- `appointment_reference.py`(신규, 순수): D-day 계산 — L1.
- 모델 `Appointment`(record), `AppointmentRepository`, DTO(`app/dtos/appointment.py`), `AppointmentService`(`app/services/appointment.py`), router `app/apis/v1/appointment_routers.py`, 프론트 전용 `AppointmentCalendarPage` + 라우트 + 진입 링크.
- **게이미피케이션 연동 없음**(일정 관리 전용 — 매일 반복 습관이 아님).

## 3. 데이터 모델 (`app/models/record.py`에 추가)
```python
class AppointmentType(StrEnum):
    """진료 일정 종류 4종."""
    CHECKUP = "CHECKUP"        # 정기 진료
    DIALYSIS = "DIALYSIS"      # 투석
    BLOOD_TEST = "BLOOD_TEST"  # 혈액검사
    OTHER = "OTHER"            # 기타


class Appointment(models.Model):
    """진료 일정 1건 = 1행 (하루 복수 가능)."""
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="appointments")
    appt_date = fields.DateField(description="진료일")
    appt_time = fields.CharField(max_length=5, null=True, description="시각 HH:MM(선택)")
    appt_type = fields.CharEnumField(enum_type=AppointmentType)
    hospital = fields.CharField(max_length=100, null=True)
    note = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "appointments"
        indexes = [("user_id", "appt_date")]
        ordering = ["appt_date", "appt_time"]
```
- `appt_time`은 TimeField의 tz 버그(Asia/Seoul) 회피 위해 "HH:MM" CharField(수면 slice와 동일 패턴).
- `aerich migrate`.

## 4. 백엔드
### 4.1 appointment_reference.py
```python
def d_day(target: date, today: date) -> int:
    """target까지 남은 일수. 오늘=0, 미래=양수, 과거=음수."""
    return (target - today).days
```
(+ L1: 미래 +N, 오늘 0, 과거 음수)

### 4.2 AppointmentRepository (record_repository.py)
- `create(user_id, appt_date, appt_time, appt_type, hospital, note) -> Appointment`
- `list_between(user_id, start: date, end: date) -> list[Appointment]` (캘린더 월 범위, 오름차순)
- `upcoming(user_id, today, limit) -> list[Appointment]` (appt_date≥today, appt_date·appt_time 오름차순, limit)
- `past(user_id, today, limit) -> list[Appointment]` (appt_date<today, 내림차순, limit)
- `get(id, user_id) -> Appointment | None`
- `update(id, user_id, **fields) -> Appointment | None` (소유권 필터, 없으면 None)
- `delete(id, user_id) -> bool` (소유권 필터)

### 4.3 AppointmentService (`app/services/appointment.py` 신규)
- `get_overview(user_id, today) -> OverviewResponse` — next(upcoming 첫 1건)+`d_day`, upcoming(최대 5), past(최근 5).
- `get_month(user_id, year, month) -> MonthResponse` — 그 달 1일~말일 `list_between` → 일정 항목 리스트(날짜·종류·병원·시각·메모·id). 프론트가 날짜별 도트·목록 구성.
- `create_appointment(user_id, dto) -> AppointmentItem`
- `update_appointment(user_id, appt_id, dto) -> AppointmentItem` — 없으면 404.
- `delete_appointment(user_id, appt_id) -> None` — 없으면 404.
- 월 범위 계산: `start = date(year, month, 1)`, `end = (start + 1달) - 1일`(`calendar.monthrange`로 말일).

### 4.4 DTO (`app/dtos/appointment.py` 신규)
`AppointmentType`은 `app.models.record`에서 import해 재사용(새로 정의 X).
```python
from app.models.record import AppointmentType
class AppointmentCreateRequest(BaseModel):
    appt_date: date
    appt_type: AppointmentType
    appt_time: str | None = None      # "HH:MM"
    hospital: str | None = None
    note: str | None = None
class AppointmentUpdateRequest(BaseModel): (동일 필드, 전체 교체)
class AppointmentItem(BaseSerializerModel):
    id: int; appt_date: date; appt_time: str | None; appt_type: AppointmentType
    hospital: str | None; note: str | None
class NextAppointment(BaseSerializerModel):
    item: AppointmentItem; d_day: int
class OverviewResponse(BaseSerializerModel):
    next: NextAppointment | None; upcoming: list[AppointmentItem]; past: list[AppointmentItem]
class MonthResponse(BaseSerializerModel):
    year: int; month: int; items: list[AppointmentItem]
class OkResponse(BaseSerializerModel):
    ok: bool   # DELETE 응답(204 대신 커스텀 fetch 클라이언트 T 반환 호환)
```
- `appt_time` 형식 검증은 프론트 `<input type="time">`에 위임(서버는 길이 5 CharField). 빈문자→None 정규화는 서비스.

### 4.5 Router (`app/apis/v1/appointment_routers.py`, prefix `/records/appointments`)
| 메서드 | 경로 | 응답 |
|---|---|---|
| GET | `/records/appointments/overview` | OverviewResponse |
| GET | `/records/appointments/month?year=&month=` | MonthResponse |
| POST | `/records/appointments` | AppointmentItem (201) |
| PUT | `/records/appointments/{id}` | AppointmentItem |
| DELETE | `/records/appointments/{id}` | OkResponse(200, {ok:true}); 미존재/타인 404 |
- `Depends(get_request_user)` 소유권. `app/apis/v1/__init__.py`에 등록.

## 5. 프론트 — 전용 `AppointmentCalendarPage` + 라우트
- `api/appointment.ts`(appointmentApi: getOverview/getMonth/create/update/delete).
- 라우트 `/records/appointments`(`PrivateRoute`) + ChallengeMainPage 진입 버튼(🧪 검사 수치 아래에 📅 병원 진료일 캘린더).
- `AppointmentCalendarPage.tsx`:
  - 루트 `flex min-h-screen flex-col bg-bg-alt`, 내부 `mx-auto w-full max-w-[28rem]`(🔥 named 너비 토큰 금지 — [[reference_tailwind_maxw_token_broken]]). 헤더(뒤로가기 `/challenge` + 제목).
  - **다음 진료 D-day 배너**: "다음 진료까지 D-3" + 종류·병원·날짜·시각. 오늘이면 "오늘", 없으면 안내.
  - **커스텀 월 그리드**: 요일 헤더(일~토) + 일자 셀(이전/다음 달 빈칸 포함), 일정 있는 날 **종류별 색 도트**. 이전/다음 달 네비 버튼. 날짜 클릭 → 그날 일정 강조 + 입력 폼 날짜 prefill.
  - **일정 추가 폼**: 날짜(`<input type="date">`) + 종류 `<select>`(정기진료/투석/혈액검사/기타) + 병원명 + 시각(`<input type="time">`, 선택) + 메모 → 추가.
  - **예정 목록**(오늘↑ 최대 5): 각 행 종류·날짜·병원·시각 + 수정/삭제. **지난 일정 아카이브**(접기 토글, 최근 5).
  - 변경 시 `["record","appointments"]` invalidate. 종류 영문 enum→한글 라벨 SSOT(`APPT_TYPE_LABELS`).

## 6. 에러
- `appt_date`·`appt_type` 필수(누락 422). 수정/삭제 소유권 없음(타인/미존재) → 404. 잘못된 `appt_type` → 422.
- 개인 일정 관리라 의료 면책 문구 없음.

## 7. 범위 외
- **시간예약 푸시 알림**(전날 18시/당일 8시) — APScheduler/cron 등 스케줄러+백그라운드 워커 필요 → 후속 슬라이스. (`Notification` 모델은 존재하나 시간 트리거 인프라 없음.)
- 캘린더 라이브러리·반복 일정·외부 캘린더(구글) 연동 — 범위 외.
- 알림 설정(시각 변경) — 푸시 연기와 함께 후속.

## 8. 테스트
- **L1**(appointment_reference): `d_day`(미래 +N, 오늘 0, 과거 음수).
- **L2**: `create`(하루 복수), `get_overview`(next D-day·upcoming 최대5·past 최근5 분리·빈 경우 next None), `get_month`(월 범위 필터), `update`/`delete` 소유권(타인 None/404 경로).
- **L3**: API overview/month/POST/PUT/DELETE, 인증·소유권, 잘못된 type 422, 타인 일정 PUT/DELETE 404.
- ⚠️ 로컬 `pytest app` 금지(운영DB drop) — CI 위임. 로컬 ruff + `python -c` + docker E2E.

## 9. 구현 순서 (writing-plans 입력)
1. AppointmentType + Appointment 모델 + `aerich migrate`
2. `appointment_reference.py` `d_day` (+L1)
3. AppointmentRepository(create/list_between/upcoming/past/get/update/delete)
4. appointment DTO (`app/dtos/appointment.py`)
5. AppointmentService (`app/services/appointment.py`)
6. appointment_routers + 등록 + L2/L3
7. 프론트 api/appointment.ts + AppointmentCalendarPage(월 그리드·D-day·목록·폼) + 라우트/진입
8. docker E2E(등록·월 도트·D-day·수정/삭제·소유권) + PR
