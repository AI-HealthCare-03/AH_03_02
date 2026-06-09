# 관리자(admin) 권한 부여 절차

팀원이 본인 계정으로 관리자 페이지(`/admin`)에 접근할 수 있도록 권한을 부여하는 절차다.

## 정책 — 왜 본인 계정에 권한을 다는가
- **감사 로그 보존**: `AdminActionLog.admin_user_id`로 누가 어떤 위험 액션을 했는지 추적할 수 있어야 한다 (사용자 비활성·정지·삭제 등). 공용 admin 계정을 공유하면 이 추적이 깨진다.
- **보안 사고 격리**: 한 팀원의 자격증명이 유출되더라도 그 계정만 차단·격리하면 끝.
- **권한 회수 단순화**: 떠나는 팀원의 권한도 한 컬럼 토글로 회수.
- **부트캠프 평가 5-4 (인증·인가)**: 계정별 권한 분리가 명확히 보이는 게 유리.

> 공용 admin 계정 공유는 **금지**한다. PR/리뷰 단계에서 발견되면 차단한다.

## 절차 (5분)

### 1) 팀원: 본인 이메일로 일반 회원가입
- 화면: `/signup`
- 이메일 인증 코드는 데모 모드라 응답에 그대로 노출됨 → 가입 즉시 인증 완료 가능.
- 가입 후 본인 사용자 ID(또는 이메일)를 권한 부여 담당자에게 전달.

### 2) 권한 부여 담당자: DB UPDATE 한 줄
로컬·개발 환경 기준 (Docker Compose):

```bash
# 단일 사용자
docker compose exec -T postgres psql -U ckduser -d ckd_challenge -c \
  "UPDATE users SET is_admin = TRUE WHERE email = 'teammate@example.com';"

# 여러 명 한 번에
docker compose exec -T postgres psql -U ckduser -d ckd_challenge -c \
  "UPDATE users SET is_admin = TRUE WHERE email IN ('a@x', 'b@x', 'c@x');"
```

`is_admin`은 `app/models/users.py:User`의 boolean 필드. JWT 토큰의 `is_admin` 클레임은 다음 로그인 시 갱신되므로, **권한 부여 후 팀원에게 재로그인을 요청**한다.

### 3) 동작 확인
```bash
# DB 상태 확인
docker compose exec -T postgres psql -U ckduser -d ckd_challenge -c \
  "SELECT id, email, is_admin FROM users WHERE is_admin = TRUE;"
```

팀원: 재로그인 후 우상단 메뉴에서 `/admin` 진입 가능해야 한다. 권한 없는 경우 403.

## 권한 회수
```bash
docker compose exec -T postgres psql -U ckduser -d ckd_challenge -c \
  "UPDATE users SET is_admin = FALSE WHERE email = 'teammate@example.com';"
```
회수 후에도 기존 JWT는 만료(15분) 전까지 유효하다. 즉시 차단이 필요하면 사용자의 `refresh_token_version`을 증가시켜 강제 로그아웃 시킨다 (REQ-SEC-003 정책).

## 운영 환경(향후)
- 본 절차는 **로컬·개발 환경 전용**이다.
- 운영 환경에서는 DB 직접 UPDATE를 금지하고, 별도의 `admin invitation` 토큰 발급 API를 통해 자동 승격하는 흐름으로 전환한다 (대시보드의 후속 작업으로 분리).

## 관련 파일
- `app/models/users.py` — `User.is_admin` 필드
- `app/dependencies/security.py` — `get_admin_user` 의존성 가드
- `app/apis/v1/admin_routers.py` — `/admin/*` 라우트 (`get_admin_user` 의존)
- `app/models/admin_action_log.py` — 위험 액션 감사 로그 (admin_user_id FK)
