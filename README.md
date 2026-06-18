# CKD 조기 발굴 및 생활습관 중재 서비스

> 만성 신장질환(CKD) 위험군을 조기에 발굴하고, 맞춤형 생활습관 챌린지로 건강 행동 변화를 유도하는 웹 서비스.
> 넥스트러너스 AI 헬스케어 3기 — Talos 참여기업 프로젝트

---

## 🎯 서비스 개요

- **타겟**: 40세 이상 성인, CKD(만성 신장질환) 위험군
- **핵심 흐름**: 건강검진 결과 입력 → ML 예측 → 그룹 배정(G1~G4) → 맞춤 챌린지 → 대시보드
- **배포 마감**: 2026-06-12 / PPT 제출: 2026-06-19
- **주요 인프라**:
  - 한국어 에러 미들웨어 (Pydantic 422 자동 변환)
  - Rate Limit (slowapi, 인증 5/분·일반 60/분)
  - 비밀번호 재설정 이메일 인증 (Resend + `EMAIL_MODE=demo|production` 토글)
  - 부하 테스트 (Locust, GET API P95 **15ms** / 동시 50명, 실패율 0%)
  - 글로벌 면책 푸터 (모든 페이지)
  - 게이미피케이션 3단계 진화 (10·40·100회, +100·400·750pt)
  - 캐릭터 일러스트 시스템 (PNG 우선, SVG fallback, 이모지 fallback)

---

## 🏗️ 아키텍처 — 6컨테이너

```
사용자 ──► nginx ──► fastapi (app/, Producer)
                         │ Redis Stream (ckd_jobs / rag_jobs)
                         ▼
                    ai-worker (ai_worker/, Consumer)
                         ├── PostgreSQL  (검진·예측결과·SHAP·AI가이드)
                         ├── Redis       (작업 큐·응답 스트림 rag_resp)
                         └── Qdrant      (RAG 벡터 DB)
```

| 컨테이너 | 역할 | 코드 위치 |
|---|---|---|
| `nginx` | 리버스 프록시 (80→8000) | `infra/nginx/` |
| `postgres` | DB | 이미지만 |
| `redis` | 메시지 브로커 (Redis Stream)·응답 스트림 | 이미지만 |
| `fastapi` ⭐ | API 서버 (Producer) | **`app/`** |
| `ai-worker` ⭐ | ML 추론(SHAP) + RAG 챗봇 | **`ai_worker/`** |
| `qdrant` | 벡터 DB (RAG) | 이미지만 |

> **Langfuse(LLM 관찰성)는 옵션** — 메인 스택과 분리된 `docker-compose.langfuse.yml`로 별도 기동(`docker compose -f docker-compose.langfuse.yml up -d` → http://localhost:3001).
> **운영(prod)**은 위 6개 + `certbot`(Let's Encrypt SSL 자동 갱신) = 7컨테이너 (`infra/docker/docker-compose.prod.yml`).

---

## 📂 폴더 구조

> 상세 가이드 → **[docs/folder-structure-guide.md](docs/folder-structure-guide.md)**

```
.
├─ app/              ← FastAPI 백엔드 (apis·services·repositories·models·dtos·tests)
├─ ai_worker/        ← AI Worker (ML 추론·LLM·RAG)
├─ src/
│  ├─ ckd/           ← ML 모델 학습 라이브러리
│  └─ rag_indexing/  ← RAG 지식 베이스 인덱싱
├─ frontend/         ← Vite + React (ckd-care-app, 완성)
├─ infra/            ← Nginx 설정·운영 Docker Compose
├─ scripts/          ← CI 스크립트 (lint·mypy·test·deploy)
├─ envs/             ← 환경변수 (.env, Git 제외)
├─ docs/             ← 프로젝트 문서
└─ docker-compose.yml
```

새 기능 = `app/` 안의 **6파일 세트**: `dtos → models → repositories → services → apis/v1 → tests`

---

## ⚙️ 로컬 실행

> 📦 **처음 셋업이라면 [SETUP.md](./SETUP.md)를 먼저 읽으세요.** `git pull`만으로는 작동하지 않습니다 — ML 모델(~5.3GB)·벡터DB(~789MB)·실제 환경변수는 GitHub에 올라가지 않아 Google Drive 등에서 별도로 받아야 합니다.

### 사전 준비

- Python 3.11 (AutoGluon 호환 — 3.13 미지원)
- [uv](https://github.com/astral-sh/uv) (패키지 매니저)
- Docker & Docker Compose

### 1. 환경변수 설정

```bash
cp envs/example.local.env envs/.local.env
# envs/.local.env 열어서 DB 비밀번호·SECRET_KEY 등 수정
```

### 2. 의존성 설치

```bash
uv sync          # 전체
uv sync --group app   # FastAPI 서버만
uv sync --group ai    # AI Worker만
```

### 3. pre-commit 훅 설치 (최초 1회)

> 커밋 직전에 ruff lint·format·공백 검사를 자동 실행해 CI 실패를 사전에 막아줍니다.

```bash
uv run pre-commit install
```

설치 후 `git commit` 할 때마다 자동으로 검사가 돌아갑니다. 전체 파일을 한 번에 검사하려면:

```bash
uv run pre-commit run --all-files
```

### 4. 전체 스택 실행 (Docker)

```bash
docker-compose up -d --build
```

실행 후 접속:
- **API Swagger**: http://localhost/api/docs

> Langfuse(LLM 트레이싱)는 옵션 — 쓰려면 별도 스택을 기동: `docker compose -f docker-compose.langfuse.yml up -d` → http://localhost:3001

### 5. 대용량 자산 + DB 마이그레이션 (ML 예측·RAG 챗봇 필수)

GitHub에 없는 모델·벡터DB를 받고 DB 스키마를 적용합니다. 자세한 절차·file ID는 [SETUP.md](./SETUP.md) 참고.

```bash
MODELS_GDRIVE_ID=<id> ./scripts/setup/fetch_models.sh    # CKD predictor (~5.3GB)
QDRANT_GDRIVE_ID=<id> ./scripts/setup/restore_qdrant.sh  # 벡터DB (~789MB)
docker compose exec fastapi uv run aerich upgrade        # DB 마이그레이션
```

### 6. 개별 실행 (개발용)

```bash
# FastAPI 서버 (포트 8001 — 부트캠프 환경 충돌 방지)
uv run uvicorn app.main:app --reload --port 8001

# AI Worker
uv run python -m ai_worker.main
```

---

## 🧪 품질 관리

```bash
pytest                                    # 테스트
uv run pre-commit run --all-files         # 린트·포맷·공백 일괄 검사 (커밋 전 권장)
ruff check . && ruff format .             # 린트·포맷만
mypy app/                                 # 타입 체크
```

또는 스크립트:

```bash
./scripts/ci/run_test.sh
./scripts/ci/code_fommatting.sh
./scripts/ci/check_mypy.sh
```

---

## 🌿 브랜치 전략 (Git Flow)

| 브랜치 | 용도 |
|---|---|
| `main` | 배포용 (보호) |
| `develop` | 통합 브랜치 |
| `feature/...` | 기능 개발 |
| `hotfix/...` | 긴급 수정 |

PR: 최소 1인 리뷰 + CI 통과 + Squash merge. 의료 콘텐츠 변경 시 `medical-review` 라벨 필수.

---

## 🔒 보안·의료 주의사항

- 혈압·혈당 수치는 **민감 건강정보** — 로그·평문 저장·외부 전송 금지
- LLM 프롬프트에 PHI(개인 건강정보) 평문 전달 금지 — 요약·범주화 후 전달
- "확진"·"치료"·"예방됩니다" 표현 금지 — "위험을 낮출 수 있다"·"관리"로만
- 이 서비스는 **임상적 의사결정 도구가 아닙니다**

---

## 📚 문서

| 문서 | 내용 |
|---|---|
| [docs/folder-structure-guide.md](docs/folder-structure-guide.md) | 폴더 구조 상세 가이드 (v1.27) |
| `.claude/CLAUDE.md` | AI 에이전트 헌장·팀 컨벤션 |
| `.claude/memory.md` | 세션 인계 문서 (결정사항·다음 할 일) |
