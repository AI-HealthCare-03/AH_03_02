# 관리자 읽기전용 임퍼소네이션 (view-as) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 관리자가 사용자관리에서 사용자를 선택해 그 사용자로 일반 화면 전체를 읽기전용으로 보는 임퍼소네이션 기능 구현.

**Architecture:** 관리자가 대상 사용자에 대한 readonly JWT(view 토큰)를 발급받아 그 토큰으로 일반 화면에 진입한다. 일반 API는 토큰 `user_id`로 조회하므로 무수정 재사용된다. 읽기전용은 인증 의존성이 쓰기 메서드를 403으로 막아 서버에서 강제한다.

**Tech Stack:** FastAPI, Tortoise ORM, 커스텀 JWT(`app/core/jwt`), React, react-query, fetch 기반 client.

스펙: `docs/superpowers/specs/2026-06-16-admin-impersonation-design.md`

---

## 파일 구조

**백엔드**
- Modify `app/models/admin_action_log.py` — `AdminAction.IMPERSONATE` 추가
- Modify `app/dtos/admin.py` — `AdminImpersonateResponse` 추가
- Modify `app/services/admin.py` — `impersonate()` 메서드 (토큰 발급 + 감사 로그)
- Modify `app/apis/v1/admin_routers.py` — `POST /admin/users/{id}/impersonate`
- Modify `app/dependencies/security.py` — readonly 토큰 쓰기 차단
- Create `app/tests/admin_apis/test_impersonation.py` — 통합 테스트

**프론트**
- Modify `frontend/ckd-care-app/src/api/admin.ts` — `impersonate()`
- Modify `frontend/ckd-care-app/src/contexts/AuthContext.tsx` — start/stopImpersonation 상태
- Modify `frontend/ckd-care-app/src/api/client.ts` — view 토큰 만료 시 admin 복귀
- Create `frontend/ckd-care-app/src/components/ImpersonationBanner.tsx` — 전역 배너
- Modify `frontend/ckd-care-app/src/pages/admin/AdminUserDetailPage.tsx` — "이 사용자로 보기" 버튼
- Modify `frontend/ckd-care-app/src/App.tsx`(또는 루트 레이아웃) — 배너 마운트

---

## Task 1: AdminAction.IMPERSONATE enum 추가

**Files:**
- Modify: `app/models/admin_action_log.py:23-32`

- [ ] **Step 1: enum 값 추가**

`AdminAction` StrEnum에 추가 (`SAFETY_EVENT_ACK` 다음 줄):
```python
    SAFETY_EVENT_ACK = "SAFETY_EVENT_ACK"
    IMPERSONATE = "IMPERSONATE"
```

- [ ] **Step 2: 마이그레이션 생성 (있으면)**

`CharEnumField`는 VARCHAR이고 컬럼 `max_length`는 기존 최장값(`USER_FORCE_VERIFY_EMAIL`, 23자)에 맞춰져 있어 `IMPERSONATE`(11자)는 들어간다. aerich가 enum 변경을 감지하면 마이그레이션이 생길 수 있다(안전, CHECK 없음).

Run: `docker compose exec -T fastapi uv run aerich migrate --name add_impersonate_action`
Expected: 마이그레이션 1건 생성 또는 "No changes detected". 생성되면 그대로 커밋.

- [ ] **Step 3: Commit**

```bash
git add app/models/admin_action_log.py app/core/db/migrations/
git commit -m "feat(admin): AdminAction.IMPERSONATE enum 추가"
```

---

## Task 2: 백엔드 — readonly 토큰 쓰기 차단 (보안 가드 먼저)

**Files:**
- Modify: `app/dependencies/security.py:13-20`
- Test: `app/tests/admin_apis/test_impersonation.py`

읽기전용 강제는 임퍼소네이션의 핵심 안전장치이므로 먼저 만든다. 토큰에 `readonly=True` 클레임이 있고 요청이 쓰기 메서드면 403.

- [ ] **Step 1: 통합 테스트 작성 (실패 예상)**

Create `app/tests/admin_apis/test_impersonation.py`:
```python
"""관리자 읽기전용 임퍼소네이션 통합 테스트. CI 격리 DB — 로컬 pytest app 금지."""

from datetime import timedelta

from httpx import ASGITransport, AsyncClient
from tortoise.contrib.test import TestCase

from app.core.jwt.tokens import AccessToken
from app.main import app

_SIGNUP = {
    "email": "imp_target@example.com", "password": "Password123!", "name": "대상자",
    "gender": "MALE", "birth_date": "1985-05-05", "phone_number": "01077778888",
}


def _readonly_token_for(user_id: int) -> str:
    token = AccessToken()
    token["user_id"] = user_id
    token["readonly"] = True
    token["impersonator"] = 999
    token.set_exp(lifetime=timedelta(minutes=30))
    return str(token)


async def _signup_and_id(client: AsyncClient) -> int:
    r = await client.post("/api/v1/auth/signup", json=_SIGNUP)
    return r.json()["user_id"]


class TestReadonlyGuard(TestCase):
    async def test_readonly_token_blocks_write(self):
        """readonly 토큰으로 쓰기(POST) → 403."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            uid = await _signup_and_id(client)
            token = _readonly_token_for(uid)
            headers = {"Authorization": f"Bearer {token}"}
            # 문진 제출(쓰기) 시도
            r = await client.post("/api/v1/lifestyle-surveys", json={
                "surveyed_date": "2026-06-16", "smoking_status": "NEVER",
                "drinking_frequency": "OCCASIONALLY", "exercise_days_per_week": 3,
                "sleep_hours_per_day": 7.0, "daily_water_intake": 1.5, "stress_level": "MODERATE",
            }, headers=headers)
        assert r.status_code == 403
        assert "읽기전용" in r.json()["detail"]

    async def test_readonly_token_allows_read(self):
        """readonly 토큰으로 읽기(GET) → 200, 대상 사용자 데이터."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            uid = await _signup_and_id(client)
            token = _readonly_token_for(uid)
            headers = {"Authorization": f"Bearer {token}"}
            r = await client.get("/api/v1/dashboard/summary", headers=headers)
        assert r.status_code == 200
```

- [ ] **Step 2: 테스트 실패 확인 (CI 또는 컨테이너)**

Run: CI(push) 또는 `docker compose exec -T fastapi uv run pytest app/tests/admin_apis/test_impersonation.py::TestReadonlyGuard -v`
Expected: `test_readonly_token_blocks_write` FAIL (현재는 readonly 무시 → 201).

- [ ] **Step 3: get_request_user에 쓰기 차단 구현**

`app/dependencies/security.py` 전체를 아래로:
```python
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.users import User
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService

security = HTTPBearer()

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def get_request_user(
    request: Request,
    credential: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    token = credential.credentials
    verified = JwtService().verify_jwt(token=token, token_type="access")
    # 읽기전용 임퍼소네이션(view-as) 토큰: 쓰기 메서드 차단(서버 강제).
    if verified.payload.get("readonly") and request.method in _WRITE_METHODS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="읽기전용 임퍼소네이션 세션에서는 데이터를 변경할 수 없습니다.",
        )
    user_id = verified.payload["user_id"]
    user = await UserRepository().get_user(user_id)
    if not user:
        raise HTTPException(detail="Authenticate Failed.", status_code=status.HTTP_401_UNAUTHORIZED)
    return user


async def get_admin_user(user: Annotated[User, Depends(get_request_user)]) -> User:
    """관리자 전용 엔드포인트 가드 (User.is_admin=True 필수)."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return user
```

- [ ] **Step 4: 테스트 통과 확인**

Run: 위 pytest 명령
Expected: `TestReadonlyGuard` 2건 PASS.

- [ ] **Step 5: ruff + commit**

```bash
docker compose exec -T fastapi ruff check app/dependencies/security.py
git add app/dependencies/security.py app/tests/admin_apis/test_impersonation.py
git commit -m "feat(admin): readonly 토큰 쓰기 차단 가드 (임퍼소네이션 안전장치)"
```

---

## Task 3: 백엔드 — 임퍼소네이션 토큰 발급 (DTO + 서비스 + 엔드포인트)

**Files:**
- Modify: `app/dtos/admin.py` (DTO 추가)
- Modify: `app/services/admin.py` (impersonate 메서드)
- Modify: `app/apis/v1/admin_routers.py` (엔드포인트)
- Test: `app/tests/admin_apis/test_impersonation.py` (클래스 추가)

- [ ] **Step 1: 통합 테스트 추가 (실패 예상)**

`test_impersonation.py`에 클래스 추가. demo 패턴이 아니라 자체 admin 계정을 DB로 만든다:
```python
from app.models.users import User


class TestImpersonateEndpoint(TestCase):
    async def test_admin_impersonate_issues_readonly_token(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 대상 사용자
            r = await client.post("/api/v1/auth/signup", json=_SIGNUP)
            target_id = r.json()["user_id"]
            # 관리자 생성 + 로그인
            admin = await User.create(
                email="imp_admin@example.com", password="x", name="관리자",
                gender="FEMALE", birthday="1980-01-01", phone_number="01000000000",
                is_admin=True, is_active=True, email_verified=True,
            )
            # 관리자 토큰 직접 발급 (로그인 우회 — 비번 해시 불필요)
            from app.services.jwt import JwtService
            admin_token = str(JwtService().create_access_token(admin))
            ah = {"Authorization": f"Bearer {admin_token}"}

            # impersonate 발급
            r = await client.post(f"/api/v1/admin/users/{target_id}/impersonate", json={}, headers=ah)
            assert r.status_code == 200
            body = r.json()
            assert "access_token" in body
            assert body["target"]["id"] == target_id

            # 발급된 view 토큰으로 읽기 200, 쓰기 403
            vh = {"Authorization": f"Bearer {body['access_token']}"}
            assert (await client.get("/api/v1/dashboard/summary", headers=vh)).status_code == 200
            w = await client.post("/api/v1/lifestyle-surveys", json={
                "surveyed_date": "2026-06-16", "smoking_status": "NEVER",
                "drinking_frequency": "OCCASIONALLY", "exercise_days_per_week": 3,
                "sleep_hours_per_day": 7.0, "daily_water_intake": 1.5, "stress_level": "MODERATE",
            }, headers=vh)
            assert w.status_code == 403

    async def test_non_admin_cannot_impersonate(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/v1/auth/signup", json=_SIGNUP)
            uid = r.json()["user_id"]
            from app.models.users import User as U
            from app.services.jwt import JwtService
            u = await U.get(id=uid)
            tok = str(JwtService().create_access_token(u))
            r = await client.post(f"/api/v1/admin/users/{uid}/impersonate", json={},
                                  headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `docker compose exec -T fastapi uv run pytest app/tests/admin_apis/test_impersonation.py::TestImpersonateEndpoint -v`
Expected: FAIL (404 — 엔드포인트 없음).

- [ ] **Step 3: DTO 추가**

`app/dtos/admin.py` — `AdminUserDetailResponse` 아래에 추가:
```python
class AdminImpersonateTarget(BaseModel):
    id: int
    name_masked: str


class AdminImpersonateResponse(BaseModel):
    """읽기전용 임퍼소네이션 view 토큰 발급 응답."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 초 단위
    target: AdminImpersonateTarget
```

- [ ] **Step 4: 서비스 메서드 추가**

`app/services/admin.py` — import에 추가:
```python
from datetime import UTC, date, datetime, timedelta  # date 이미 있으면 유지
from app.core.jwt.tokens import AccessToken
```
`force_verify_email` 메서드 다음에 추가:
```python
    async def impersonate(self, *, admin_user_id: int, user_id: int) -> dict:
        """대상 사용자에 대한 읽기전용 view 토큰 발급 + 감사 로그.

        view 토큰: access 토큰에 readonly=True, impersonator=admin_id, 30분 만료.
        일반 API는 토큰 user_id로 조회하므로 그 사용자 화면을 그대로 보게 된다.
        쓰기는 get_request_user의 readonly 가드가 403으로 막는다.
        """
        user = await User.get_or_none(id=user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
        ttl = timedelta(minutes=30)
        token = AccessToken()
        token["user_id"] = user.id
        token["readonly"] = True
        token["impersonator"] = admin_user_id
        token.set_exp(lifetime=ttl)
        async with in_transaction():
            await self._log(
                admin_user_id=admin_user_id,
                action=AdminAction.IMPERSONATE,
                target_type=TargetType.USER,
                target_id=user_id,
                detail={"impersonator": admin_user_id},
            )
        return {
            "access_token": str(token),
            "token_type": "bearer",
            "expires_in": int(ttl.total_seconds()),
            "target": {"id": user.id, "name_masked": mask_name(user.name)},
        }
```
(`AdminAction`은 이미 import됨. `mask_name`도 이미 import됨.)

- [ ] **Step 5: 엔드포인트 추가**

`app/apis/v1/admin_routers.py` — import에 `AdminImpersonateResponse` 추가, 사용자 관리 섹션에 추가:
```python
@admin_router.post(
    "/users/{user_id}/impersonate",
    response_model=AdminImpersonateResponse,
    status_code=status.HTTP_200_OK,
    summary="사용자 임퍼소네이션 (읽기전용 view 토큰 발급, 감사 로그)",
)
async def impersonate_user(
    user_id: int,
    admin: Annotated[User, Depends(get_admin_user)],
    service: Annotated[AdminService, Depends(AdminService)],
) -> Response:
    result = await service.impersonate(admin_user_id=admin.id, user_id=user_id)
    return Response(content=result, status_code=status.HTTP_200_OK)
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `docker compose exec -T fastapi uv run pytest app/tests/admin_apis/test_impersonation.py -v`
Expected: 4건 모두 PASS.

- [ ] **Step 7: ruff format + commit**

```bash
docker compose exec -T fastapi ruff check app/services/admin.py app/dtos/admin.py app/apis/v1/admin_routers.py
# 호스트에서 직접 ruff format (컨테이너 format은 호스트 미반영 — 메모리 교훈)
cd <repo> && uv run ruff format app/services/admin.py app/dtos/admin.py app/apis/v1/admin_routers.py
git add app/dtos/admin.py app/services/admin.py app/apis/v1/admin_routers.py
git commit -m "feat(admin): 임퍼소네이션 view 토큰 발급 엔드포인트 + 감사 로그"
```

---

## Task 4: 프론트 — admin.ts impersonate API

**Files:**
- Modify: `frontend/ckd-care-app/src/api/admin.ts`

- [ ] **Step 1: 타입 + 메서드 추가**

인터페이스 추가:
```typescript
export interface ImpersonateResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  target: { id: number; name_masked: string };
}
```
`adminApi` 객체에 추가:
```typescript
  impersonate: (id: number) => api.post<ImpersonateResponse>(`/admin/users/${id}/impersonate`, {}),
```

- [ ] **Step 2: 빌드 확인**

Run: `npm --prefix frontend/ckd-care-app run build`
Expected: 빌드 성공.

- [ ] **Step 3: Commit**

```bash
git add frontend/ckd-care-app/src/api/admin.ts
git commit -m "feat(admin): impersonate API 클라이언트 메서드"
```

---

## Task 5: 프론트 — AuthContext 임퍼소네이션 상태

**Files:**
- Modify: `frontend/ckd-care-app/src/contexts/AuthContext.tsx`

view 토큰은 sessionStorage `access_token`에 두고(탭 닫으면 소멸), admin 토큰은 `admin_token_backup`에 백업한다. 새로고침 생존을 위해 임퍼소네이션 메타도 sessionStorage에 둔다.

- [ ] **Step 1: 상태 + 메서드 구현**

`AuthContext.tsx`의 `AuthContextValue`에 추가:
```typescript
  isImpersonating: boolean;
  impersonationTarget: { id: number; name_masked: string } | null;
  startImpersonation: (viewToken: string, target: { id: number; name_masked: string }) => Promise<void>;
  stopImpersonation: () => Promise<void>;
```
`AuthProvider` 내부, `login` 위에 상수/상태 추가:
```typescript
const ADMIN_BACKUP_KEY = "admin_token_backup";
const IMPERSONATION_KEY = "impersonation_target";
```
```typescript
  const [impersonationTarget, setImpersonationTarget] =
    useState<{ id: number; name_masked: string } | null>(() => {
      const raw = sessionStorage.getItem(IMPERSONATION_KEY);
      return raw ? JSON.parse(raw) : null;
    });
```
`login` 아래에 메서드 추가:
```typescript
  async function startImpersonation(viewToken: string, target: { id: number; name_masked: string }) {
    const adminToken = localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
    if (adminToken) sessionStorage.setItem(ADMIN_BACKUP_KEY, adminToken);
    sessionStorage.setItem(IMPERSONATION_KEY, JSON.stringify(target));
    setImpersonationTarget(target);
    // view 토큰은 비영속(sessionStorage)으로 — login(persistent=false)이 캐시 clear + 토큰 저장 + me() 수행
    await login(viewToken, false);
  }

  async function stopImpersonation() {
    const adminToken = sessionStorage.getItem(ADMIN_BACKUP_KEY);
    sessionStorage.removeItem(ADMIN_BACKUP_KEY);
    sessionStorage.removeItem(IMPERSONATION_KEY);
    setImpersonationTarget(null);
    if (adminToken) {
      await login(adminToken, true); // 관리자 토큰 복원(영속) + 캐시 clear
    } else {
      logout();
    }
  }
```
Provider value에 추가:
```typescript
    value={{ user, token, login, logout, isLoading,
             isImpersonating: !!impersonationTarget, impersonationTarget,
             startImpersonation, stopImpersonation }}
```

- [ ] **Step 2: 빌드 확인**

Run: `npm --prefix frontend/ckd-care-app run build`
Expected: 성공.

- [ ] **Step 3: Commit**

```bash
git add frontend/ckd-care-app/src/contexts/AuthContext.tsx
git commit -m "feat(admin): AuthContext 임퍼소네이션 시작/종료 상태"
```

---

## Task 6: 프론트 — view 토큰 만료 시 admin 자동 복귀 (client.ts 함정 처리)

**Files:**
- Modify: `frontend/ckd-care-app/src/api/client.ts:106-131`

**문제:** `request`는 401 시 `tryRefresh`(refresh 쿠키 = admin의 것)로 admin access를 받아 silent 복귀시킨다. 임퍼소네이션 중에는 view 토큰이 refresh 없이 30분 만료되므로, 이 경로가 혼란을 준다. 임퍼소네이션 중 401이면 refresh하지 말고 admin 토큰으로 즉시 복원한다.

- [ ] **Step 1: 401 핸들러 분기 추가**

`request` 함수의 `if (res.status === 401) {` 블록 **맨 앞**에 추가:
```typescript
  if (res.status === 401) {
    // 임퍼소네이션(view 토큰) 만료: refresh 쿠키는 관리자 것이므로 refresh하지 않고
    // 백업한 관리자 토큰으로 복원한 뒤 관리자 화면으로 보낸다.
    const adminBackup = sessionStorage.getItem("admin_token_backup");
    if (adminBackup) {
      sessionStorage.removeItem("admin_token_backup");
      sessionStorage.removeItem("impersonation_target");
      localStorage.setItem("access_token", adminBackup);
      sessionStorage.removeItem("access_token");
      window.location.href = "/admin/users";
      throw new Error("임퍼소네이션 세션이 만료돼 관리자로 돌아갑니다.");
    }
    const newToken = await tryRefresh();
    // ... 기존 코드 유지
```

- [ ] **Step 2: 빌드 확인**

Run: `npm --prefix frontend/ckd-care-app run build`
Expected: 성공.

- [ ] **Step 3: Commit**

```bash
git add frontend/ckd-care-app/src/api/client.ts
git commit -m "fix(admin): 임퍼소네이션 view 토큰 만료 시 관리자 복원(refresh 우회)"
```

---

## Task 7: 프론트 — ImpersonationBanner + 진입 버튼 + 마운트

**Files:**
- Create: `frontend/ckd-care-app/src/components/ImpersonationBanner.tsx`
- Modify: `frontend/ckd-care-app/src/pages/admin/AdminUserDetailPage.tsx`
- Modify: `frontend/ckd-care-app/src/App.tsx` (루트 — 정확한 파일은 라우터 루트를 확인)

- [ ] **Step 1: 배너 컴포넌트 생성**

Create `ImpersonationBanner.tsx`:
```tsx
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export function ImpersonationBanner() {
  const { isImpersonating, impersonationTarget, stopImpersonation } = useAuth();
  const navigate = useNavigate();
  if (!isImpersonating || !impersonationTarget) return null;
  return (
    <div className="sticky top-0 z-50 flex items-center justify-between gap-3 bg-amber-500 px-4 py-2 text-sm font-bold text-slate-900">
      <span>👁 관리자 보기 중 · {impersonationTarget.name_masked}님 (읽기전용)</span>
      <button
        type="button"
        onClick={async () => { await stopImpersonation(); navigate("/admin/users"); }}
        className="rounded-md bg-slate-900 px-3 py-1 text-xs font-bold text-amber-300 hover:bg-slate-800"
      >
        관리자로 돌아가기
      </button>
    </div>
  );
}
```

- [ ] **Step 2: 루트에 마운트**

라우터 루트(App.tsx 또는 공통 레이아웃)의 최상단에 `<ImpersonationBanner />`를 렌더. 라우트 트리 안, `AuthProvider`·`BrowserRouter` 하위여야 한다(useAuth·useNavigate 필요). 정확한 위치는 기존 라우터 구조를 따른다.

- [ ] **Step 3: "이 사용자로 보기" 버튼 추가**

`AdminUserDetailPage.tsx` — `useAuth`·`useNavigate` import. "관리자 액션" 섹션의 버튼들 옆에 추가:
```tsx
<button
  type="button"
  onClick={async () => {
    try {
      const res = await adminApi.impersonate(userId);
      await startImpersonation(res.access_token, res.target);
      navigate("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "임퍼소네이션 실패");
    }
  }}
  className="rounded-md bg-indigo-500 px-[12px] py-[6px] text-xs font-bold text-white hover:bg-indigo-400"
>
  이 사용자로 보기 (읽기전용)
</button>
```
컴포넌트 상단에서 `const { startImpersonation } = useAuth(); const navigate = useNavigate();`.

- [ ] **Step 4: 빌드 확인**

Run: `npm --prefix frontend/ckd-care-app run build`
Expected: 성공.

- [ ] **Step 5: Commit**

```bash
git add frontend/ckd-care-app/src/components/ImpersonationBanner.tsx frontend/ckd-care-app/src/pages/admin/AdminUserDetailPage.tsx frontend/ckd-care-app/src/App.tsx
git commit -m "feat(admin): 임퍼소네이션 배너 + 사용자 상세 진입 버튼"
```

---

## Task 8: E2E 검증 (배포 후, 운영 데이터 영향 없이)

**Files:** 없음 (검증 전용)

- [ ] **Step 1: 머지·배포 후 API E2E**

demo(admin) 토큰 → 홍길동(id=1) impersonate → view 토큰으로:
- `GET /api/v1/dashboard/summary` → 200, 홍길동 데이터
- `POST /api/v1/lifestyle-surveys` → 403
- 감사 로그 `GET /admin/logs?action=IMPERSONATE` → 1건

Run: 점검 스크립트(이전 패턴의 python urllib) 또는 사이트에서 직접 시연.
Expected: 위 결과대로.

- [ ] **Step 2: 사이트 수동 시연**

demo 로그인 → 관리자 → 사용자관리 → 홍길동 → "이 사용자로 보기" → 배너 표시 + 홍길동 대시보드 → 쓰기 비활성 → "관리자로 돌아가기" → 관리자 복귀.

---

## Self-Review 체크

- **R1**(사용자 선택→일반 화면): Task 3(토큰)+Task 7(버튼)+무수정 일반 API ✅
- **R2**(읽기전용): Task 2(서버 쓰기 403) ✅
- **R3**(일반 API 무수정): view 토큰 user_id 조회 ✅
- **R4**(감사 로그): Task 1(enum)+Task 3(_log) ✅
- **R5**(admin만): 엔드포인트 get_admin_user 가드 + Task 3 비-admin 403 테스트 ✅
- **R6**(표시·복귀): Task 7 배너 + stopImpersonation ✅
- 함정(view 토큰 만료 refresh): Task 6 처리 ✅
