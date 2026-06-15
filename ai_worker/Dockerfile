FROM python:3.11-slim

WORKDIR /app

# 1. uv 설치 (공식 이미지에서 복사해오는 가장 깔끔한 방법)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. 의존성 패키지 관리 파일을 컨테이너 내부에 복사합니다.
COPY pyproject.toml uv.lock ./

# 3. ai(ML)·rag(RAG 추론) 그룹 설치. redis 등 project 기본 의존성도 포함됨.
#    rag 그룹이 있어야 ai_worker.rag(langchain·langgraph·qdrant·openai)가 import 된다.
RUN uv sync --group ai --group rag --no-dev --frozen

# 3-1. AutoGluon predictor 추론용 — ai 그룹(torch)과 lock 충돌을 피하려 pyproject 밖에서 직접 설치.
#      (autogluon stable이 requires-python>=3.11 전체를 만족 못 해 uv.lock 통합 resolve 실패하기 때문)
RUN uv pip install "autogluon.tabular" lightgbm xgboost

# 3-2. asyncpg — ai_worker가 health_checks를 직접 UPDATE(core/db.py)하는 데 필요.
#      pyproject에서 app 그룹에만 있어 base/ai/rag sync로는 설치되지 않으므로 명시 설치.
RUN uv pip install asyncpg

# 4. ai_worker·src(CKD predict 모듈) 패키지 복사.
COPY ./ai_worker ./ai_worker
COPY ./src ./src

# 5. RAG Redis Stream consumer 기동 (rag_jobs 처리 → rag_resp:{job_id}).
#    --no-sync: 빌드 시 sync된 venv 그대로 사용. 미설정 시 매 시작마다 default group만 재sync해서
#    ai/rag 그룹 패키지(pymupdf4llm·openai·qdrant-client 등) 제거됨.
CMD ["uv", "run", "--no-sync", "python", "-m", "ai_worker.main"]
