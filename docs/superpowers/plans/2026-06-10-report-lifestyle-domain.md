# 생활습관 개선항목 도메인 분리 (Phase B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 리포트 생활습관 개선항목을 식이/운동/기타 도메인으로 묶고 도메인별 한 줄 요약을 제공한다.

**Architecture:** 백엔드는 `clinical_reference.py`에 도메인 매핑·요약 순수함수 추가(SSOT), `health_check.py`가 항목에 domain을 채우고 도메인별 요약 DTO를 조립한다. 프론트는 이미 존재하는 `LifestyleSummaryCard`(현재 "domain 없어 생략" 주석)를 도메인 그루핑으로 채운다. DB 마이그레이션 없음(DTO·서비스 레이어만).

**Tech Stack:** FastAPI · Tortoise ORM · Pydantic · React + TypeScript + Vite · pytest · ruff

> ⚠️ **로컬 검증 규칙 (메모리 기준, 반드시 준수)**
> - `pytest app`을 로컬에서 돌리지 말 것 — conftest autouse DB fixture가 운영 postgres(ckd_challenge)를 DROP함.
> - 순수 모듈(`test_clinical_reference.py`)은 conftest 범위 밖이라 로컬 `pytest` 안전.
> - DTO·서비스 검증은 `python -c`(컨테이너: `docker compose exec fastapi python -c '...'`)로. pytest는 CI에 맡김.
> - 커밋 메시지에 `$(cat <<EOF ...)` heredoc-in-$() 금지 (bkit 훅 차단). 여러 `-m` 사용.
> - 프론트 dev 중 새 dep 설치 금지(이번 작업은 새 라이브러리 없음).

---

## File Structure

| 파일 | 책임 | 변경 |
|---|---|---|
| `app/services/clinical_reference.py` | 도메인 매핑·라벨·요약문구 (순수 SSOT) | 상수 3개 + 함수 2개 추가 |
| `app/services/test_clinical_reference.py` | 순수 모듈 단위 테스트 | 테스트 클래스 2개 추가 |
| `app/dtos/health_check.py` | 리포트 DTO | `LifestyleItem.domain` + `LifestyleDomainSummary` + `ReportResponse` 필드 |
| `app/tests/health_check_apis/test_report_dto.py` | DTO 직렬화 테스트 | 직렬화 테스트 + keys 갱신 |
| `app/services/health_check.py` | 리포트 빌드 서비스 | import + domain 채움 + 요약 staticmethod + get_report 통합 |
| `frontend/.../src/api/healthCheck.ts` | API 타입 | `domain` + `LifestyleDomainSummary` + `ReportResponse` 필드 |
| `frontend/.../src/pages/LLMActionGuidePage.tsx` | 리포트 UI | `LifestyleSummaryCard` 도메인 그루핑 |

---

## Task 1: 도메인 매핑·요약 순수함수 (clinical_reference)

**Files:**
- Modify: `app/services/clinical_reference.py` (상수: `M2_LABEL` 블록 뒤 ~line 206 다음 / 함수: 파일 끝 `m2_maintain_msg` 뒤 ~line 558)
- Test: `app/services/test_clinical_reference.py`

- [ ] **Step 1: 실패 테스트 작성** — `test_clinical_reference.py` import 줄(7~21)에 `build_domain_summary_text`, `m2_domain` 추가하고 파일 끝에 클래스 2개 추가

```python
class TestM2Domain:
    def test_diet_features(self):
        for f in ["bmi", "waist_cm", "hdl_cholesterol", "ldl_cholesterol", "triglycerides"]:
            assert m2_domain(f) == "diet"

    def test_exercise_features(self):
        for f in ["sitting_hours", "walking_days", "moderate_days", "vigorous_days"]:
            assert m2_domain(f) == "exercise"

    def test_etc_feature(self):
        assert m2_domain("smoking_current") == "etc"

    def test_unknown_defaults_etc(self):
        assert m2_domain("unknown_feature") == "etc"


class TestBuildDomainSummaryText:
    def test_empty_is_good(self):
        assert build_domain_summary_text([]) == "양호합니다"

    def test_single_label(self):
        assert build_domain_summary_text(["중성지방"]) == "중성지방 관리가 필요합니다"

    def test_multiple_labels(self):
        assert (
            build_domain_summary_text(["LDL 콜레스테롤", "중성지방"])
            == "LDL 콜레스테롤·중성지방 관리가 필요합니다"
        )
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && python -m pytest app/services/test_clinical_reference.py -q`
Expected: FAIL — `ImportError: cannot import name 'm2_domain'`

- [ ] **Step 3: 상수 추가** — `clinical_reference.py` `M2_LABEL = { ... }` 블록(195~206) 바로 뒤에 삽입

```python
# 모델2 생활습관 도메인 분류 (식이/운동/기타) — Phase B
M2_DOMAIN = {
    "bmi": "diet",
    "waist_cm": "diet",
    "hdl_cholesterol": "diet",
    "ldl_cholesterol": "diet",
    "triglycerides": "diet",
    "sitting_hours": "exercise",
    "walking_days": "exercise",
    "moderate_days": "exercise",
    "vigorous_days": "exercise",
    "smoking_current": "etc",
}
DOMAIN_LABEL = {"diet": "식이", "exercise": "운동", "etc": "기타"}
DOMAIN_ORDER = ["diet", "exercise", "etc"]
```

- [ ] **Step 4: 함수 추가** — 파일 끝(`m2_maintain_msg` 정의 뒤)에 삽입

```python
def m2_domain(feature: str) -> str:
    """생활습관 feature의 도메인(diet/exercise/etc) 반환. 미정의는 etc."""
    return M2_DOMAIN.get(feature, "etc")


def build_domain_summary_text(improve_labels: list[str]) -> str:
    """도메인 개선항목 라벨 → 한 줄 요약. 빈 리스트는 '양호합니다'."""
    if not improve_labels:
        return "양호합니다"
    return f"{'·'.join(improve_labels)} 관리가 필요합니다"
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest app/services/test_clinical_reference.py -q`
Expected: PASS (기존 테스트 포함 전부 green)

- [ ] **Step 6: 커밋**

```bash
git add app/services/clinical_reference.py app/services/test_clinical_reference.py
git commit -m "feat(report): 생활습관 도메인 매핑·요약 순수함수 추가 (Phase B)" -m "M2_DOMAIN/DOMAIN_LABEL/DOMAIN_ORDER + m2_domain + build_domain_summary_text. 순수 모듈 단위테스트 동반(로컬 pytest 안전)." -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: DTO 확장 (health_check DTO)

**Files:**
- Modify: `app/dtos/health_check.py` (`LifestyleItem` 119~129 / `ReportResponse` 148~158)
- Test: `app/tests/health_check_apis/test_report_dto.py`

- [ ] **Step 1: 실패 테스트 작성** — `test_report_dto.py` 끝에 직렬화 테스트 추가 + `test_report_response_keys`의 기대 키 집합에 `"lifestyle_domain_summary"` 추가

```python
def test_lifestyle_domain_summary_serialization() -> None:
    """LifestyleDomainSummary 직렬화."""
    from app.dtos.health_check import LifestyleDomainSummary

    s = LifestyleDomainSummary(
        domain="diet",
        domain_label="식이",
        improve_count=2,
        summary="LDL 콜레스테롤·중성지방 관리가 필요합니다",
    )
    d = s.model_dump()
    assert d["domain"] == "diet"
    assert d["domain_label"] == "식이"
    assert d["improve_count"] == 2
    assert d["summary"].endswith("관리가 필요합니다")


def test_lifestyle_item_has_domain() -> None:
    """LifestyleItem.domain 기본값 빈 문자열."""
    from app.dtos.health_check import LifestyleItem

    it = LifestyleItem(
        feature="ldl_cholesterol", label="LDL 콜레스테롤", normal_range="<130",
        value_text="150.0", status="높음", status_level="danger",
        group="improve", action="포화지방을 줄이세요", domain="diet",
    )
    assert it.model_dump()["domain"] == "diet"
```

`test_report_response_keys`의 기대 집합을 다음으로 교체:
```python
    assert keys == {
        "health_check_id",
        "shap_model1",
        "shap_model2",
        "ai_guide",
        "recommended_tests",
        "model1_summary",
        "clinical_items",
        "lifestyle_items",
        "report_meta",
        # Phase B: 생활습관 도메인 요약
        "lifestyle_domain_summary",
    }
```

- [ ] **Step 2: 테스트 실패 확인 (python -c, DB 없이)**

Run:
```bash
python -c "from app.dtos.health_check import LifestyleDomainSummary"
```
Expected: FAIL — `ImportError: cannot import name 'LifestyleDomainSummary'`

- [ ] **Step 3: DTO 구현** — `LifestyleItem`에 `domain` 추가

```python
class LifestyleItem(BaseModel):
    """모델2 생활습관 항목 상세 (리포트 생활습관 상세표)."""

    feature: str
    label: str
    normal_range: str
    value_text: str
    status: str
    status_level: str
    group: str  # improve | maintain
    action: str = ""  # 개선 시 행동 제안 (improve 항목)
    domain: str = ""  # diet | exercise | etc (Phase B)
```

`LifestyleItem` 클래스 바로 뒤에 신규 DTO:
```python
class LifestyleDomainSummary(BaseModel):
    """생활습관 도메인별 핵심요약 (Phase B). 항상 식이/운동/기타 3개."""

    domain: str          # diet | exercise | etc
    domain_label: str    # 식이 | 운동 | 기타
    improve_count: int   # 해당 도메인 개선 필요 항목 수
    summary: str         # 규칙 기반 한 줄
```

`ReportResponse`에 필드 추가 (`lifestyle_items` 뒤):
```python
    lifestyle_items: list[LifestyleItem] = []
    lifestyle_domain_summary: list[LifestyleDomainSummary] = []
    report_meta: ReportMeta | None = None
```

- [ ] **Step 4: 검증 (python -c)**

Run:
```bash
python -c "from app.dtos.health_check import LifestyleDomainSummary, ReportResponse; r=ReportResponse(health_check_id=1, shap_model1=[], shap_model2=None, ai_guide=''); print('lifestyle_domain_summary' in r.model_dump())"
```
Expected: `True`

- [ ] **Step 5: 커밋**

```bash
git add app/dtos/health_check.py app/tests/health_check_apis/test_report_dto.py
git commit -m "feat(report): LifestyleItem.domain + LifestyleDomainSummary DTO (Phase B)" -m "ReportResponse에 lifestyle_domain_summary 추가(기본 []). 직렬화 테스트·keys 갱신. 하위호환(기본값)." -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 서비스 통합 (health_check)

**Files:**
- Modify: `app/services/health_check.py` (import 19~35 / `_build_lifestyle_items` ~560 / `get_report` 649~690)

- [ ] **Step 1: import 추가** — clinical_reference import 블록(19~35)에 알파벳 순으로 추가

```python
from app.services.clinical_reference import (
    DOMAIN_LABEL,
    DOMAIN_ORDER,
    build_domain_summary_text,
    # ... 기존 m1_*, m2_* 유지 ...
    m2_domain,
    # ...
)
```
그리고 DTO import 블록에 `LifestyleDomainSummary` 추가 (기존 `LifestyleItem` 옆).

- [ ] **Step 2: `_build_lifestyle_items`에 domain 채움** — `items.append(LifestyleItem(...))` 호출의 마지막 인자로 추가

```python
            items.append(
                LifestyleItem(
                    feature=feature,
                    label=m2_label(feature),
                    normal_range=nr,
                    value_text=vtext,
                    status=status_label,
                    status_level=status_level,
                    group=group,
                    action=action,
                    domain=m2_domain(feature),
                )
            )
```

- [ ] **Step 3: 요약 staticmethod 추가** — `_build_lifestyle_items` 메서드 바로 뒤에 삽입

```python
    @staticmethod
    def _build_lifestyle_domain_summary(
        items: list[LifestyleItem],
    ) -> list[LifestyleDomainSummary]:
        """생활습관 항목을 도메인별로 묶어 핵심요약 생성. 항상 DOMAIN_ORDER 3개.

        improve 그룹 라벨을 모아 한 줄 요약. 개선항목 0건 도메인은 '양호합니다'.
        """
        summaries: list[LifestyleDomainSummary] = []
        for domain in DOMAIN_ORDER:
            improve_labels = [
                it.label for it in items if it.domain == domain and it.group == "improve"
            ]
            summaries.append(
                LifestyleDomainSummary(
                    domain=domain,
                    domain_label=DOMAIN_LABEL[domain],
                    improve_count=len(improve_labels),
                    summary=build_domain_summary_text(improve_labels),
                )
            )
        return summaries
```

- [ ] **Step 4: `get_report` 통합** — `lifestyle_items` 빌드 뒤에 요약 빌드 추가, `ReportResponse`에 필드 전달

```python
        lifestyle_items = self._build_lifestyle_items(hc, ls, gender_int)
        lifestyle_domain_summary = self._build_lifestyle_domain_summary(lifestyle_items)
        report_meta = self._build_report_meta(hc, user, ls)

        return ReportResponse(
            health_check_id=hc.id,
            shap_model1=shap_list,
            shap_model2=hc.shap_model2,
            ai_guide=hc.ai_guide or "",
            recommended_tests=recommended,
            model1_summary=summary,
            clinical_items=clinical_items,
            lifestyle_items=lifestyle_items,
            lifestyle_domain_summary=lifestyle_domain_summary,
            report_meta=report_meta,
        )
```

- [ ] **Step 5: 검증 (컨테이너 python -c — 순수 staticmethod 호출)**

Run:
```bash
docker compose exec -T fastapi python -c 'from app.dtos.health_check import LifestyleItem; from app.services.health_check import HealthCheckService; items=[LifestyleItem(feature="ldl_cholesterol",label="LDL 콜레스테롤",normal_range="",value_text="",status="",status_level="",group="improve",action="",domain="diet"),LifestyleItem(feature="triglycerides",label="중성지방",normal_range="",value_text="",status="",status_level="",group="improve",action="",domain="diet"),LifestyleItem(feature="smoking_current",label="흡연 여부",normal_range="",value_text="",status="",status_level="",group="maintain",action="",domain="etc")]; out=HealthCheckService._build_lifestyle_domain_summary(items); print([(s.domain,s.improve_count,s.summary) for s in out])'
```
Expected: `[('diet', 2, 'LDL 콜레스테롤·중성지방 관리가 필요합니다'), ('exercise', 0, '양호합니다'), ('etc', 0, '양호합니다')]`

- [ ] **Step 6: ruff + 커밋**

```bash
ruff check app/services/health_check.py && ruff format app/services/health_check.py
git add app/services/health_check.py
git commit -m "feat(report): get_report에 생활습관 도메인 요약 통합 (Phase B)" -m "_build_lifestyle_items에 domain 채움 + _build_lifestyle_domain_summary(항상 3개) + 응답 반영." -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 프론트 API 타입 (healthCheck.ts)

**Files:**
- Modify: `frontend/ckd-care-app/src/api/healthCheck.ts` (`LifestyleItem` 93~102 / `ReportResponse` 118~128)

- [ ] **Step 1: `LifestyleItem`에 domain 추가**

```typescript
export interface LifestyleItem {
  feature: string;
  label: string;
  normal_range: string;
  value_text: string;
  status: string;
  status_level: "good" | "info" | "caution" | "warnLight" | "danger";
  group: "improve" | "maintain";
  action: string;
  domain: string; // diet | exercise | etc (Phase B)
}
```

- [ ] **Step 2: 신규 타입 추가** — `LifestyleItem` 뒤

```typescript
export interface LifestyleDomainSummary {
  domain: string;
  domain_label: string;
  improve_count: number;
  summary: string;
}
```

- [ ] **Step 3: `ReportResponse`에 필드 추가**

```typescript
export interface ReportResponse {
  health_check_id: number;
  shap_model1: ShapItem1[];
  shap_model2: LifestyleShap | null;
  ai_guide: string;
  recommended_tests?: string[];
  model1_summary?: string;
  clinical_items?: ClinicalItem[];
  lifestyle_items?: LifestyleItem[];
  lifestyle_domain_summary?: LifestyleDomainSummary[];
  report_meta?: ReportMeta | null;
}
```

- [ ] **Step 4: 타입체크**

Run: `cd frontend/ckd-care-app && npx tsc -b`
Expected: exit 0 (에러 없음)

- [ ] **Step 5: 커밋**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/api/healthCheck.ts
git commit -m "feat(report): API 타입에 domain·LifestyleDomainSummary 추가 (Phase B)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 프론트 도메인 그루핑 UI (LLMActionGuidePage)

**Files:**
- Modify: `frontend/ckd-care-app/src/pages/LLMActionGuidePage.tsx` (import 21 근처 / `LifestyleSummaryCard` 676~733 / 호출부)

- [ ] **Step 1: import 추가** — `LifestyleItem` import 줄(21 근처)에 `LifestyleDomainSummary` 추가

```typescript
  LifestyleItem,
  LifestyleDomainSummary,
```

- [ ] **Step 2: `LifestyleSummaryCard` 교체** — 676~733의 함수와 그 위 NOTE 주석(676~678)을 아래로 전부 교체

```tsx
// ===== 생활습관 핵심 요약 카드 (도메인별: 식이/운동/기타) =====
function LifestyleSummaryCard({
  items,
  domainSummary,
}: {
  items: LifestyleItem[];
  domainSummary: LifestyleDomainSummary[];
}) {
  if (items.length === 0) return null;

  const improveOf = (domain: string) =>
    items.filter((it) => it.domain === domain && it.group === "improve");

  return (
    <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-sm">
      <p className="text-sm font-bold text-text-primary">생활습관 핵심 요약</p>
      <div className="flex flex-col gap-[10px]">
        {domainSummary.map((d) => {
          const improveItems = improveOf(d.domain);
          return (
            <div key={d.domain} className="flex flex-col gap-[6px]">
              <div className="flex flex-wrap items-center gap-[8px]">
                <span className="text-sm font-semibold text-text-primary">{d.domain_label}</span>
                <span
                  className="rounded-full px-[8px] py-[2px] text-xs font-semibold"
                  style={
                    d.improve_count > 0
                      ? { backgroundColor: "#fee2e2", color: "#DC2626" }
                      : { backgroundColor: "#dcfce7", color: "#16A34A" }
                  }
                >
                  {d.improve_count > 0 ? `개선 필요 ${d.improve_count}개` : "양호"}
                </span>
                <span className="text-sm leading-[1.6] text-text-secondary">{d.summary}</span>
              </div>
              {improveItems.length > 0 && (
                <ul className="flex flex-col gap-[4px] pl-[10px]">
                  {improveItems.map((it) => (
                    <li key={it.feature} className="flex items-start gap-[8px]">
                      <span className="mt-[6px] h-[5px] w-[5px] shrink-0 rounded-full bg-[#DC2626]" />
                      <span className="text-sm leading-[1.6] text-text-secondary">
                        <span className="font-medium text-text-primary">{it.label}</span>
                        {it.action ? ` — ${it.action}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 호출부에 domainSummary 전달** — `<LifestyleSummaryCard` 사용처를 grep으로 찾아 prop 추가

Run: `grep -n "LifestyleSummaryCard" frontend/ckd-care-app/src/pages/LLMActionGuidePage.tsx`

호출부(JSX)를 다음 형태로 수정 (report 데이터 변수명은 해당 파일 컨벤션 따름, 예 `report`/`data`):
```tsx
<LifestyleSummaryCard
  items={report.lifestyle_items ?? []}
  domainSummary={report.lifestyle_domain_summary ?? []}
/>
```

- [ ] **Step 4: 타입체크 + 빌드**

Run: `cd frontend/ckd-care-app && npx tsc -b && npm run build`
Expected: tsc exit 0, vite build 성공

- [ ] **Step 5: 커밋**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/pages/LLMActionGuidePage.tsx
git commit -m "feat(report): 생활습관 핵심요약 카드를 식이/운동/기타 도메인 그루핑으로 (Phase B)" -m "기존 LifestyleSummaryCard의 'domain 없어 생략' 자리 구현. 상세표(LifestyleDetailTable)는 불변." -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 통합 검증 + PR 준비

**Files:** (검증만, 코드 변경 없음 — 발견 이슈 있으면 해당 Task로 복귀)

- [ ] **Step 1: 백엔드 lint 전체**

Run: `ruff check app && ruff format --check app`
Expected: All checks passed

- [ ] **Step 2: 순수 단위 테스트 (로컬 안전)**

Run: `python -m pytest app/services/test_clinical_reference.py -q`
Expected: PASS

- [ ] **Step 3: 프론트 타입체크 + 빌드**

Run: `cd frontend/ckd-care-app && npx tsc -b && npm run build`
Expected: 성공

- [ ] **Step 4: (선택) docker E2E — 실제 리포트 응답 확인**

백엔드 컨테이너 reload 후, 테스트 계정(e2e_test@example.com / Test1234!)으로 로그인해 리포트 조회 → 응답 JSON에 `lifestyle_domain_summary`가 3개(diet/exercise/etc) 들어오는지, 프론트 핵심요약 카드가 3개 도메인으로 렌더되는지 확인.
- 프론트: `cd frontend/ckd-care-app && npm run dev` → http://localhost:5173 → 리포트 페이지(/llm-guide)
- 주의: ai-worker rebuild 불필요(서비스 레이어 변경, fastapi reload로 반영). 컨테이너 코드가 볼륨 마운트가 아니면 `docker compose up -d --build fastapi` 필요할 수 있음.

- [ ] **Step 5: 변경 요약 + PR (push/PR 생성은 주니 승인 시)**

```bash
git log --oneline origin/develop..HEAD
```
머지는 주니 명시 시에만. PR 생성도 주니 지시 후.

---

## Self-Review (작성 후 점검)

**Spec coverage:**
- ✅ §4.1 SSOT → Task 1 (M2_DOMAIN/DOMAIN_LABEL/DOMAIN_ORDER/m2_domain) + 요약문구 함수
- ✅ §4.2 DTO → Task 2 (LifestyleItem.domain, LifestyleDomainSummary, ReportResponse)
- ✅ §4.3 요약 생성 → Task 1(문구) + Task 3(도메인 그룹핑·항상 3개)
- ✅ §4.4 프론트 → Task 4(타입) + Task 5(LifestyleSummaryCard 그루핑)
- ✅ §4.5 테스트 → Task 1(m2_domain) + Task 2(DTO keys/직렬화)
- ✅ §5 결정(3분류/0건 양호/별도카드/domain명/규칙템플릿) 전부 반영
- ✅ §6 엣지(ls 없음 → improve 0 → "양호") = `_build_lifestyle_domain_summary`가 항목 없는 도메인도 항상 생성

**Type consistency:** `domain`(소문자 diet/exercise/etc) 일관, `LifestyleDomainSummary`{domain, domain_label, improve_count, summary} 백/프론트 동일, `build_domain_summary_text`/`m2_domain` 명칭 Task 1·3 일치.

**Placeholder scan:** 모든 step에 실제 코드/명령 포함. 호출부 prop 추가(Task 5 Step 3)는 변수명만 파일 컨벤션 의존 — grep 명령으로 위치 특정.
