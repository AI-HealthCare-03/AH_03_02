import os
import uuid
import zoneinfo
from dataclasses import field
from enum import StrEnum
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Env(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENV: Env = Env.LOCAL
    SECRET_KEY: str = f"default-secret-key{uuid.uuid4().hex}"
    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))
    TEMPLATE_DIR: str = os.path.join(Path(__file__).resolve().parent.parent, "templates")

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "ckduser"
    DB_PASSWORD: str = "ckdpass1234"
    DB_NAME: str = "ckd_challenge"
    DB_CONNECT_TIMEOUT: int = 5
    DB_CONNECTION_POOL_MAXSIZE: int = 10

    # Redis (RAG 챗봇 작업 큐 — docker-compose redis 서비스)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    RAG_JOBS_STREAM: str = "rag_jobs"  # 백엔드→worker 작업 스트림
    RAG_JOBS_GROUP: str = "rag_workers"  # consumer group 이름
    RAG_RESP_PREFIX: str = "rag_resp"  # 응답 채널 prefix → rag_resp:{job_id}
    RAG_TIMEOUT_SEC: int = 60  # 백엔드 응답 대기 상한
    CKD_JOBS_STREAM: str = "ckd_jobs"  # 백엔드→worker CKD 예측 작업 스트림

    COOKIE_DOMAIN: str = "localhost"

    JWT_ALGORITHM: str = "HS256"
    # v0.7 / REQ-SEC-003: Access 15분 / Refresh 7일 (Rotate). 단위는 둘 다 '분'으로 통일 — tokens.py에서 timedelta(minutes=...)로 사용
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 7 * 24 * 60  # 10080분 = 7일
    JWT_LEEWAY: int = 5

    # 프론트엔드 URL (이메일 인증·비번 재설정 링크 발송에 사용)
    FRONTEND_URL: str = "http://localhost:5173"

    # 이메일 (REQ-AUTH 비밀번호 재설정 + REQ-AUTH-003 회원가입 인증)
    # EMAIL_MODE:
    #   demo       = 응답에 코드 노출, 외부 호출 X (시연 안전, 발표 기본값)
    #   gmail      = Gmail SMTP 실제 발송 + 응답에도 코드 노출(시연 fallback 유지)
    #                — SMTP_USERNAME/SMTP_PASSWORD 미설정 시 demo로 강등
    #   production = Resend API 실제 발송, 응답 코드 null
    #                — RESEND_API_KEY 미설정 시 demo로 강등
    EMAIL_MODE: str = "demo"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "CKD Care <onboarding@resend.dev>"
    # Gmail SMTP (EMAIL_MODE=gmail 일 때 사용)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""  # 본인 Gmail 주소
    SMTP_PASSWORD: str = ""  # Gmail 앱 비밀번호 (16자, 2FA 활성화 후 발급)
    PASSWORD_RESET_CODE_TTL_SECONDS: int = 300  # 5분
    PASSWORD_RESET_MAX_ATTEMPTS: int = 5

    # Rate limiting (REQ-NF-008). 기본 켜짐 — 단일 IP 부하테스트 등에서만 false 로 비활성화
    RATE_LIMIT_ENABLED: bool = True

    @model_validator(mode="after")
    def _enforce_real_secret_key(self) -> "Config":
        # REQ-SEC: dev/prod에서 SECRET_KEY가 기본값/placeholder면 부팅 실패(fail-fast).
        # 미설정 시 매 프로세스 랜덤 키로 조용히 동작 → 멀티워커 토큰 검증 붕괴·재시작 시 세션 전멸하는 footgun 방지.
        # 로컬(LOCAL)은 개발 편의상 허용.
        if self.ENV in (Env.DEV, Env.PROD) and (
            self.SECRET_KEY.startswith("default-secret-key") or self.SECRET_KEY.startswith("CHANGE_ME")
        ):
            raise ValueError("SECRET_KEY must be set to a real secret in dev/prod (no default/placeholder value)")
        # REQ-AUTH-003: prod에서 EMAIL_MODE=demo면 인증/재설정 코드가 API 응답(demo_code)에 노출 → 부팅 실패
        if self.ENV == Env.PROD and self.EMAIL_MODE == "demo":
            raise ValueError("EMAIL_MODE must not be 'demo' in prod (인증/재설정 코드가 응답에 노출됨)")
        return self
