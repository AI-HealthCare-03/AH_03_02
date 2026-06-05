FROM python:3.11-slim

WORKDIR /app

# 1. uv 설치 (공식 이미지에서 복사해오는 가장 깔끔한 방법)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. 의존성 패키지 관리 파일을 컨테이너 내부에 복사합니다.
COPY pyproject.toml uv.lock ./

# 3. ai(ML)·rag(RAG 추론) 그룹 설치. redis 등 project 기본 의존성도 포함됨.
#    rag 그룹이 있어야 ai_worker.rag(langchain·langgraph·qdrant·openai)가 import 된다.
RUN uv sync --group ai --group rag --no-dev --frozen

# 4. ai_worker 패키지를 그대로 복사 (python -m ai_worker.main 모듈 경로 유지).
COPY ./ai_worker ./ai_worker

# 5. RAG Redis Stream consumer 기동 (rag_jobs 처리 → rag_resp:{job_id}).
CMD ["uv", "run", "python", "-m", "ai_worker.main"]
