import zoneinfo
from dataclasses import field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    RAG_JOBS_STREAM: str = "rag_jobs"
    RAG_JOBS_GROUP: str = "rag_workers"
    RAG_RESP_PREFIX: str = "rag_resp"

    # CKD 비동기 예측 작업 큐
    CKD_JOBS_STREAM: str = "ckd_jobs"
    CKD_JOBS_GROUP: str = "ckd_workers"

    # Postgres (worker가 health_checks를 직접 UPDATE — asyncpg)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "ckduser"
    DB_PASSWORD: str = "ckdpass1234"
    DB_NAME: str = "ckd_challenge"
