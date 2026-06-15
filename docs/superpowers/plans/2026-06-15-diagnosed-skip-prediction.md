# 진단자 예측·리포트 스킵 (모듈 ①) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CKD 진단자(ckd_diagnosed=True)에게는 ML 위험도 예측·SHAP·AI 리포트 가이드를 생성하지 않고, 리포트 조회 시 비대상 플래그를 내려준다.

**Architecture:** `create_health_check`에서 진단자면 예측 job 발행을 스킵(=예측·SHAP·가이드가 자동으로 안 생김, ai_worker 무수정). `get_report`는 `ReportMeta.report_available` 플래그로 진단자(app_group∈{CKD,DIALYSIS})를 비대상 표시. 모듈 ②(프론트)가 이 플래그를 소비.

**Tech Stack:** FastAPI, Tortoise ORM, pytest, ruff, uv, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-06-15-diagnosed-skip-prediction-design.md`

---

## 사전 주의 (반드시 준수)

- **로컬 `pytest app` 절대 금지** — conftest의 autouse DB fixture가 운영 postgres(ckd_challenge)를 DROP하는 사고 이력 있음. 로컬 검증은 `ruff` lint + `uv run python -c "..."` 만. DB 기반 테스트(`tortoise.contrib.test.TestCase`)는 **CI(격리)** 에 위임.
- 테스트는 두 위치에 있다: `app/tests/**` 와 `app/services/test_*.py`. 본 작업은 `app/tests/health_check_apis/` 를 쓴다.
- 작업 브랜치: `feat/diagnosed-skip-prediction` (이미 생성됨, develop=`99cd77b` 기준).
- `git add -A` 금지 — 변경 파일만 명시적으로 stage (untracked `.gstack/`·`data/`·`data_pipeline/` 혼입 방지).

---

## File Structure

| 종류 | 파일 | 책임 |
|------|------|------|
| Modify | `app/services/health_check.py` | ① `create_health_check` 발행 가드 ② `_build_report_meta` report_available 계산 |
| Modify | `app/dtos/health_check.py` | `ReportMeta`에 `report_available: bool` 필드 추가 |
| Modify | `app/tests/health_check_apis/test_report_dto.py` | `_build_report_meta` 진단자 플래그 단위테스트(DB 미접근) |
| Modify | `app/tests/health_check_apis/test_health_check_api.py` | 진단자 발행 스킵 통합테스트(CI 위임) |
| 무수정 | `ai_worker/**` | 변경 없음 |

---

## Task 1: 리포트 플래그 — ReportMeta.report_available

진단자(app_group ∈ {CKD, DIALYSIS})면 `report_available=False`. DB 미접근이라 로컬 `python -c` 로 검증 가능 → 먼저 한다.

**Files:**
- Modify: `app/dtos/health_check.py:142-155` (ReportMeta)
- Modify: `app/services/health_check.py:684-696` (_build_report_meta 반환부)
- Test: `app/tests/health_check_apis/test_report_dto.py`

- [ ] **Step 1: ReportMeta DTO에 필드 추가**

`app/dtos/health_check.py` — `ReportMeta` 클래스 마지막 필드(`peer_relative: str | None`) 바로 아래에 추가:

```python
    peer_top_pct: int | None
    peer_relative: str | None
    report_available: bool = True  # 진단자(CKD/DIALYSIS)면 False — 위험도 예측·리포트 비대상
```

- [ ] **Step 2: 실패 테스트 작성**

`app/tests/health_check_apis/test_report_dto.py` 파일 맨 아래에 추가:

```python
def test_report_meta_available_default_true() -> None:
    """ReportMeta.report_available 기본값은 True(비진단자)."""
    from app.dtos.health_check import ReportMeta

    meta = ReportMeta(
        group="G4",
        group_title="건강 습관 형성군",
        grade="낮음",
        score=3.0,
        group_message="msg",
        age=45,
        gender="남성",
        conditions=[],
        family_history=[],
        peer_top_pct=None,
        peer_relative=None,
    )
    assert meta.report_available is True


def test_build_report_meta_unavailable_for_diagnosed() -> None:
    """_build_report_meta — 진단자(CKD/DIALYSIS)는 report_available=False, 비진단자(G4)는 True."""
    from app.models.health_check import AppGroup, HealthCheck
    from app.models.users import Gender, User
    from app.services.health_check import HealthCheckService

    def _hc(group: AppGroup) -> HealthCheck:
        return HealthCheck(
            app_group=group,
            ckd_risk_score=None,
            shap_model1=None,
            shap_model2=None,
            egfr_estimated=None,
        )

    user = User(gender=Gender.MALE, birthday=None)

    assert HealthCheckService._build_report_meta(_hc(AppGroup.G4), user, None).report_available is True
    assert HealthCheckService._build_report_meta(_hc(AppGroup.CKD), user, None).report_available is False
    assert HealthCheckService._build_report_meta(_hc(AppGroup.DIALYSIS), user, None).report_available is False
```

- [ ] **Step 3: 테스트가 실패하는지 로컬 검증 (DB 미접근, python -c)**

Run (코드 디렉토리에서):
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
uv run python -c "
from app.models.health_check import AppGroup, HealthCheck
from app.models.users import Gender, User
from app.services.health_check import HealthCheckService
hc = HealthCheck(app_group=AppGroup.CKD, ckd_risk_score=None, shap_model1=None, shap_model2=None, egfr_estimated=None)
u = User(gender=Gender.MALE, birthday=None)
m = HealthCheckService._build_report_meta(hc, u, None)
print('report_available =', getattr(m, 'report_available', 'MISSING'))
"
```
Expected: `AttributeError` 또는 `report_available = MISSING` (아직 _build_report_meta가 필드를 안 넘김 → 기본값 True가 나오면 진단자 케이스 미반영 상태).

- [ ] **Step 4: _build_report_meta 반환부에 report_available 추가**

`app/services/health_check.py` — `_build_report_meta`의 `return ReportMeta(...)`(라인 684-696)에서 `peer_relative=peer_relative,` 다음 줄에 추가. `group_str`은 같은 함수 라인 641에서 이미 계산됨:

```python
        return ReportMeta(
            group=group_str,
            group_title=m1_group_title(letter),
            grade=grade,
            score=score,
            group_message=m1_group_message(letter),
            age=age,
            gender=gender_str,
            conditions=conditions,
            family_history=family_hist,
            peer_top_pct=peer_top_pct,
            peer_relative=peer_relative,
            report_available=group_str not in ("CKD", "DIALYSIS"),
        )
```

- [ ] **Step 5: 로컬 검증 (python -c) — 통과 확인**

Run:
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
uv run python -c "
from app.models.health_check import AppGroup, HealthCheck
from app.models.users import Gender, User
from app.services.health_check import HealthCheckService
u = User(gender=Gender.MALE, birthday=None)
def hc(g): return HealthCheck(app_group=g, ckd_risk_score=None, shap_model1=None, shap_model2=None, egfr_estimated=None)
print('G4 ->', HealthCheckService._build_report_meta(hc(AppGroup.G4), u, None).report_available)
print('CKD ->', HealthCheckService._build_report_meta(hc(AppGroup.CKD), u, None).report_available)
print('DIALYSIS ->', HealthCheckService._build_report_meta(hc(AppGroup.DIALYSIS), u, None).report_available)
"
```
Expected:
```
G4 -> True
CKD -> False
DIALYSIS -> False
```

- [ ] **Step 6: ruff lint**

Run:
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
uv run ruff check app/dtos/health_check.py app/services/health_check.py app/tests/health_check_apis/test_report_dto.py
uv run ruff format --check app/dtos/health_check.py app/services/health_check.py app/tests/health_check_apis/test_report_dto.py
```
Expected: `All checks passed!` (format 실패 시 `uv run ruff format <파일>` 후 재확인 — CI는 format도 검사)

- [ ] **Step 7: Commit**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add app/dtos/health_check.py app/services/health_check.py app/tests/health_check_apis/test_report_dto.py
git commit -m "feat: 리포트 조회에 진단자 비대상 플래그(report_available) 추가

진단자(app_group CKD/DIALYSIS)는 report_available=False.
모듈 ②(대시보드/리포트 프론트)가 이 값으로 리포트 비대상 안내."
```

---

## Task 2: 발행 가드 — 진단자 예측 job 스킵

진단자(ckd_diagnosed=True) 검진 저장 시 `publish_ckd_job`을 호출하지 않는다. DB(TestCase) 통합테스트라 **로컬 실행 금지 → CI 위임**. 로컬은 ruff + import 검증만.

**Files:**
- Modify: `app/services/health_check.py:225-238` (create_health_check 발행부)
- Test: `app/tests/health_check_apis/test_health_check_api.py`

- [ ] **Step 1: 발행 스킵 통합테스트 작성**

`app/tests/health_check_apis/test_health_check_api.py` 파일 맨 아래에 추가. `ckd_publisher.publish_ckd_job`을 spy로 monkeypatch하고, 진단자/비진단자 LifestyleSurvey를 만들어 검진 POST 후 호출 여부를 검증:

```python
class TestDiagnosedSkipsPrediction(TestCase):
    async def _signup_login(self, client: AsyncClient) -> tuple[int, str]:
        await client.post("/api/v1/auth/signup", json=_SIGNUP_DATA)
        resp = await client.post("/api/v1/auth/login", json=_LOGIN_DATA)
        token = resp.json()["access_token"]
        from app.models.users import User

        user = await User.get(email=_SIGNUP_DATA["email"])
        return user.id, token

    async def test_diagnosed_user_skips_publish(self):
        """ckd_diagnosed=True면 예측 job 발행을 스킵한다."""
        from app.models.lifestyle_survey import LifestyleSurvey
        from app.services import health_check as hc_service

        calls: list = []

        async def _spy(**kwargs):
            calls.append(kwargs)

        from unittest.mock import patch

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            user_id, token = await self._signup_login(client)
            await LifestyleSurvey.create(
                user_id=user_id,
                surveyed_date="2026-05-19",
                ckd_diagnosed=True,
            )
            with patch.object(hc_service.ckd_publisher, "publish_ckd_job", _spy):
                resp = await client.post(
                    "/api/v1/health-checks",
                    json=_HEALTH_CHECK_PAYLOAD,
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == status.HTTP_201_CREATED
        assert calls == []  # 진단자 → 발행 스킵

    async def test_nondiagnosed_user_publishes(self):
        """ckd_diagnosed=False(설문 없음)면 예측 job을 발행한다."""
        from app.services import health_check as hc_service

        calls: list = []

        async def _spy(**kwargs):
            calls.append(kwargs)

        from unittest.mock import patch

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            _user_id, token = await self._signup_login(client)
            with patch.object(hc_service.ckd_publisher, "publish_ckd_job", _spy):
                resp = await client.post(
                    "/api/v1/health-checks",
                    json=_HEALTH_CHECK_PAYLOAD,
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == status.HTTP_201_CREATED
        assert len(calls) == 1  # 비진단자 → 발행
```

참고: `LifestyleSurvey.create`에 필수 필드가 더 있으면(NOT NULL) 모델 정의를 확인해 기본값을 채운다. `ckd_diagnosed`만 본 테스트의 분기 입력이다.

- [ ] **Step 2: 발행 가드 구현**

`app/services/health_check.py` — `create_health_check`의 발행 블록(라인 225-238)을 `if not ckd_diagnosed:` 로 감싼다. `ckd_diagnosed`는 라인 190에 이미 계산되어 있음:

```python
        # 비동기 CKD 예측 job 발행 — 진단자는 스킵(이미 의료영역, 위험도 예측·리포트 비대상)
        if not ckd_diagnosed:
            try:
                await ckd_publisher.publish_ckd_job(
                    health_check_id=hc.id,
                    user_id=user_id,
                    user_age=user_age,
                    user_gender=user_gender,
                    checked_date=dto.checked_date,
                    bmi=bmi,
                    egfr=egfr,
                    dto=dto,
                )
            except Exception:  # noqa: BLE001 — 예측 발행 실패가 검진 API를 깨지 않도록
                logger.exception("CKD 예측 job 발행 실패 — 검진은 저장됨 hc=%s", hc.id)
        else:
            logger.info("CKD 진단자 — 예측 job 미발행(위험도·리포트 비대상) hc=%s", hc.id)
```

- [ ] **Step 3: 로컬 import·구문 검증 (DB 미접근)**

Run:
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
uv run python -c "import app.services.health_check; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 4: ruff lint**

Run:
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
uv run ruff check app/services/health_check.py app/tests/health_check_apis/test_health_check_api.py
uv run ruff format --check app/services/health_check.py app/tests/health_check_apis/test_health_check_api.py
```
Expected: `All checks passed!` (format 실패 시 `uv run ruff format <파일>`)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add app/services/health_check.py app/tests/health_check_apis/test_health_check_api.py
git commit -m "feat: CKD 진단자는 예측 job 발행 스킵

create_health_check에서 ckd_diagnosed=True면 publish_ckd_job 미호출.
진단자는 위험도 예측·SHAP·AI가이드 생성 안 함(이미 의료영역).
ai_worker 무수정 — job 자체가 발행되지 않아 자동 스킵."
```

---

## Task 3: 검증 (docker E2E) + push

ai_worker 무수정 → rebuild 불필요. `fastapi`는 app 볼륨 마운트라 restart로 충분.

- [ ] **Step 1: fastapi restart**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
docker compose restart fastapi
```
(주니의 로컬 docker가 실행 중이어야 함. 미실행이면 이 단계는 주니에게 요청.)

- [ ] **Step 2: 진단자 E2E 확인**

진단자 계정(ckd_diagnosed=True 문진 입력)으로 검진 저장 후:
- fastapi 로그에 `CKD 진단자 — 예측 job 미발행` 출력 확인
- DB `health_checks`에서 해당 행의 `ckd_risk_score`·`shap_model1`·`shap_model2`·`ai_guide` NULL, `app_group`이 CKD 또는 DIALYSIS 확인:
```bash
docker compose exec postgres psql -U ckduser -d ckd_challenge -c \
  "SELECT id, app_group, ckd_risk_score, ai_guide IS NULL AS guide_null FROM health_checks ORDER BY id DESC LIMIT 3;"
```
- 리포트 조회 API 응답의 `report_meta.report_available == false` 확인

- [ ] **Step 3: 비진단자 회귀 확인**

비진단자 계정으로 검진 저장 → `ckd_jobs` 정상 발행 → 예측·SHAP·가이드 생성, `report_meta.report_available == true` 확인.

- [ ] **Step 4: push (PR은 주니 승인 후)**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git push -u origin feat/diagnosed-skip-prediction
```
CI(lint + 격리 pytest)가 green인지 확인. **develop 머지는 주니 명시 "머지해줘" 후에만** — 그 전엔 PR 생성까지만(또는 push까지만).

---

## Self-Review (작성자 체크)

- **Spec 커버리지**: 발행 가드(Task 2) ✅ / 리포트 플래그(Task 1) ✅ / 테스트(Task 1·2) ✅ / E2E 검증(Task 3) ✅ / 범위밖(②③·백필) 명시 ✅.
- **Placeholder**: 없음. `LifestyleSurvey.create` 필수필드는 "모델 확인" 단서만 — 구현자가 모델에서 확인(과한 선반영 회피).
- **Type 일관성**: `report_available: bool` (DTO) ↔ `group_str not in ("CKD","DIALYSIS")` (service, bool) 일치. `ckd_diagnosed`(bool, 라인 190) ↔ `if not ckd_diagnosed` 일치.
