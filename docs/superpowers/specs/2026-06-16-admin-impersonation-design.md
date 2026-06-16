# 관리자 읽기전용 임퍼소네이션 (view-as) 설계

- 날짜: 2026-06-16
- 상태: 설계 승인 대기
- 작성: brainstorming 세션 (EC2 관리자 모드 점검 후속)

## 1. 개요 / 목적

관리자가 **사용자관리에서 사용자를 선택**하면, 그 사용자로 로그인한 것처럼 **일반 화면 전체(대시보드·리포트·검진이력·문진이력·챌린지)를 그 사용자 데이터로 본다.** 고객 지원, 디버깅, 사용자 검진·문진 결과 확인이 목적이다.

핵심 제약은 **읽기 전용**이다. 관리자는 그 사용자 화면을 보기만 하고, 어떤 데이터도 변경할 수 없다.

## 2. 요구사항

| # | 요구사항 |
|---|---|
| R1 | 관리자가 사용자를 선택해 그 사용자로 일반 화면 전체를 본다 |
| R2 | **읽기 전용** — 임퍼소네이션 세션에서는 모든 쓰기(검진 입력·문진 수정·챌린지 참여 등) 차단 |
| R3 | 일반 화면/일반 API는 **무수정**으로 재사용 (그 사용자 데이터 자동 반영) |
| R4 | 임퍼소네이션 행위는 **감사 로그**에 영구 기록 |
| R5 | 관리자(`is_admin=true`)만 임퍼소네이션 가능 |
| R6 | 임퍼소네이션 중임이 화면에 명확히 표시되고, 한 번에 관리자로 복귀 가능 |

## 3. 아키텍처

방식: **읽기전용 view-as 토큰**. 관리자가 대상 사용자에 대한 읽기전용 JWT를 발급받아, 그 토큰으로 일반 화면에 진입한다. 일반 API는 토큰의 `sub`(=대상 user_id)로 조회하므로 무수정 재사용된다.

### 3.1 백엔드

**(a) `AdminAction` enum 확장** — `app/models/admin_action_log.py`
- `IMPERSONATE` 액션 추가. aerich 마이그레이션 1건(enum=VARCHAR 확장이라 CHECK 없음, 안전).

**(b) 임퍼소네이션 엔드포인트** — `app/apis/v1/admin_routers.py`
- `POST /admin/users/{user_id}/impersonate` (`get_admin_user` 가드)
- 흐름:
  1. 대상 사용자 존재 확인 (404)
  2. 대상 제한 없음 — 일반·관리자 사용자 모두 임퍼소네이션 허용(읽기전용이라 안전). 자기 자신 대상도 막지 않음(무의미하나 무해).
  3. **읽기전용 view 토큰 발급**: JWT 클레임
     - `sub = user_id` (대상 사용자)
     - `impersonator = admin.id`
     - `readonly = true`
     - `exp = 30분` (짧게)
  4. `AdminActionLog` 기록: `action=IMPERSONATE`, `target_type=USER`, `target_id=user_id`, `detail={impersonator: admin.id}`
- 응답 DTO: `{ access_token, token_type, expires_in, target: { id, name_masked } }`
- 토큰 발급은 기존 access 토큰 생성 함수 재사용 + `readonly`/`impersonator` 클레임 추가 (`app/dependencies/security.py` 또는 auth 토큰 유틸).

**(c) 읽기전용 강제 (서버 가드)** — `app/dependencies/security.py` `get_request_user`
- 토큰 디코드 시 `readonly` 클레임 추출.
- **요청 메서드가 쓰기(POST/PATCH/PUT/DELETE)이고 `readonly=true`이면 403** ("읽기전용 임퍼소네이션 세션에서는 변경할 수 없습니다").
- GET/HEAD는 통과 → 토큰 `sub`로 일반 조회.
- 예외 없음(모든 쓰기 차단). 임퍼소네이션 종료는 프론트의 토큰 폐기이므로 서버 상태 불필요.
- `request.method` 접근을 위해 의존성에 `Request` 주입.

**(d) 기존 일반 API**: 무수정. 토큰 `sub`만 대상 사용자라 자동으로 그 사용자 데이터를 조회한다.

### 3.2 프론트

**(a) `api/admin.ts`**: `impersonate(userId)` → `POST /admin/users/{id}/impersonate` → `{ access_token, target }`.

**(b) `contexts/AuthContext`**: 임퍼소네이션 상태 관리
- `startImpersonation(viewToken, target)`:
  - 현재 admin access 토큰을 `sessionStorage["admin_token_backup"]`에 저장
  - 토큰 저장소를 `viewToken`으로 교체
  - 임퍼소네이션 메타(`target`, `readonly`) 저장
  - **`queryClient.clear()`** — 이전(관리자) 캐시 분리 (계정 전환 캐시 잔존 버그 교훈)
- `stopImpersonation()`:
  - view 토큰 폐기 → `admin_token_backup` 복원 → 백업 제거
  - 임퍼소네이션 메타 해제
  - **`queryClient.clear()`** → 관리자 화면으로 navigate
- 새로고침 생존: 임퍼소네이션 메타와 백업을 `sessionStorage`에 두어 탭 새로고침에도 유지(탭 닫으면 소멸).

**(c) 진입 버튼** — `pages/admin/AdminUserDetailPage.tsx` (+ 선택적으로 목록 행)
- "이 사용자로 보기" 버튼 → `impersonate` → `startImpersonation` → `/dashboard`로 이동.

**(d) 전역 배너** — 신규 `components/ImpersonationBanner.tsx`
- 임퍼소네이션 중 상단 고정: `👁 관리자 보기 중 · {target.name}님 (읽기전용) · [관리자로 돌아가기]`
- 앱 루트(`App` 또는 공통 레이아웃)에 배치, 임퍼소네이션 상태일 때만 렌더.
- "관리자로 돌아가기" → `stopImpersonation`.

**(e) 쓰기 버튼 비활성화 (UX)**: 임퍼소네이션 상태면 검진 입력·문진 제출·챌린지 체크인 등 쓰기 CTA를 disabled 처리. 서버 403이 최종 방어, 이건 사용자 혼란 방지용 UX.

## 4. 데이터 플로우

```
관리자 로그인(admin 토큰)
  → 사용자관리 → 사용자 선택 → [이 사용자로 보기]
  → POST /admin/users/{id}/impersonate  (admin 토큰)
  → view 토큰(sub=대상, readonly=true, 30분) + 감사로그 기록
  → admin 토큰 백업 → 토큰=view 토큰 → queryClient.clear()
  → /dashboard 진입 → 일반 API들이 view 토큰 sub로 조회 → 대상 사용자 데이터 표시
  → (쓰기 시도 시 서버 403)
  → [관리자로 돌아가기] → view 토큰 폐기 → admin 토큰 복원 → queryClient.clear() → 관리자 화면
```

## 5. 보안

- view 토큰 **30분 만료**로 노출 창 최소화.
- **읽기전용은 서버에서 강제**(쓰기 403) — 프론트 비활성화는 보조.
- 임퍼소네이션 발급은 `get_admin_user` 가드 → 관리자만.
- 의료 **PHI 전체가 노출**되는 강력한 권한이므로, 발급 시점이 `AdminActionLog`에 영구 기록되어 사후 추적 가능.
- 토큰 전환 시 `queryClient.clear()`로 관리자↔대상 캐시 격리(이전 계정 데이터 잔존 방지).

## 6. 테스트 전략

CI 격리 DB 통합 테스트(`tortoise.contrib.test.TestCase`), 로컬 pytest app 금지.
- **권한**: 비-admin이 `/admin/users/{id}/impersonate` → 403.
- **발급**: admin → 200, 응답에 토큰·target. 감사로그에 `IMPERSONATE` 1건.
- **읽기전용 강제**: view 토큰으로 GET(대시보드 summary 등) → 200 + **대상 사용자 데이터**. view 토큰으로 쓰기(예: 문진 POST) → **403**.
- **격리**: 임퍼소네이션 종료 후 admin 토큰으로 관리자 API 정상.

## 7. 범위 밖 (YAGNI)

- 쓰기 가능 임퍼소네이션
- 임퍼소네이션 중첩(임퍼소네이션 중 또 다른 사용자)
- 일반 사용자의 타인 데이터 조회
- 임퍼소네이션 세션 서버측 화이트리스트/강제 종료(만료로 충분)

## 8. 백로그 — 추가 관리자 기능 제안 (이번 범위 아님)

점검에서 도출된 보강 후보:
- **검진/문진 이력 직접 조회** — 현재 상세는 최신 1건 범주 요약만. (임퍼소네이션으로 일부 대체됨)
- **CSV 내보내기** — 사용자/통계 데이터 추출
- **안전 이벤트 알림** — `safety_events` 신규 발생 시 관리자 알림
