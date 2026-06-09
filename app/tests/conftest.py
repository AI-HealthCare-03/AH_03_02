import asyncio
import os
import socket
from collections.abc import Generator

import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest
from tortoise.contrib.test import finalizer, initializer

from app.core import config
from app.core.db.databases import TORTOISE_APP_MODELS
from app.core.rate_limit import limiter
from app.services.auth import AuthService

# 테스트 중에는 Rate Limit 비활성화 (단일 IP에서 빠르게 호출하므로 5/min 초과)
limiter.enabled = False

# REQ-AUTH-003 회귀 회피: 테스트에서 로그인 직전에 사용자를 자동 인증 처리.
# 운영 정책(미인증자 로그인 403 차단)이 인증 외 기능 테스트를 깨뜨리므로,
# AuthService.authenticate 진입 시점에 email_verified=True로 자동 갱신한다.
# - signup 라우터 안에서 발송되는 인증 코드 응답 흐름은 패치 영향 X
# - 인증 자체 테스트(test_signup_api 등)는 이 패치 전에 처리되는 응답을 검증한다
_original_authenticate = AuthService.authenticate


async def _auto_verify_then_authenticate(self: AuthService, data):  # type: ignore[no-untyped-def]
    user = await self.user_repo.get_user_by_email(str(data.email))
    if user and not user.email_verified and not user.hashed_password.startswith("SOCIAL:"):
        user.email_verified = True
        await user.save(update_fields=["email_verified"])
    return await _original_authenticate(self, data)


AuthService.authenticate = _auto_verify_then_authenticate  # type: ignore[method-assign]

# 테스트는 외부 메일 발송을 하지 않는다. .local.env의 EMAIL_MODE가 gmail/production이어도
# EmailService를 demo로 강제 — 응답에 코드 포함이 단정인 기존 테스트(test_signup_api·test_password_reset)
# 회귀 방지.
from app.services.email import EmailService  # noqa: E402

_original_email_init = EmailService.__init__


def _force_demo_email_init(self) -> None:  # type: ignore[no-untyped-def]
    _original_email_init(self)
    self._mode = "demo"


EmailService.__init__ = _force_demo_email_init  # type: ignore[method-assign]

TEST_BASE_URL = "http://test"


def _resolve_db_host(host: str) -> str:
    """Docker 외부(로컬 머신)에서 실행 시 호스트명이 미해결되면 localhost로 자동 대체.
    CI(GitHub Actions)와 Docker 컨테이너 내부에서는 'postgres' 그대로 사용."""
    try:
        socket.getaddrinfo(host, None)
        return host
    except socket.gaierror:
        return "localhost"


# PostgreSQL에서 DB를 생성/삭제하려면 다른 DB(maintenance DB)에 먼저 접속해야 한다.
# asyncpg는 DB 미지정 시 username(ckduser)을 DB명으로 사용하므로,
# CI의 postgres 서비스에 ckduser DB가 존재해야 한다. (checks.yml 참고)
_db_host = _resolve_db_host(config.DB_HOST)

# 테스트 전용 DB — dev DB와 분리해 pytest 실행 시 사용자/검진/포인트 데이터 보호
# (tortoise initializer는 매 세션 시작 시 drop_database/create_database를 수행 → dev DB 와이프 차단)
# 기본값: {DB_NAME}_test (예: ckd_challenge_test). 환경변수 TEST_DB_NAME으로 override 가능.
_TEST_DB_NAME = os.getenv("TEST_DB_NAME") or f"{config.DB_NAME}_test"
TEST_DB_URL = f"postgres://{config.DB_USER}:{config.DB_PASSWORD}@{_db_host}:{config.DB_PORT}/{_TEST_DB_NAME}"


async def _ensure_test_database_exists_async() -> None:
    """pytest 부팅 직전에 test DB 존재 보장. 없으면 maintenance DB(ckduser)에 붙어 CREATE.

    docker/postgres/init.sql은 컨테이너 최초 부팅 시만 실행되므로,
    기존 컨테이너를 그대로 쓰는 팀원 환경에서도 이 폴백이 안전망 역할을 한다.
    """
    import asyncpg

    conn = await asyncpg.connect(
        host=_db_host,
        port=int(config.DB_PORT),
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_USER,  # maintenance DB (ckduser)
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", _TEST_DB_NAME)
        if not exists:
            # CREATE DATABASE는 트랜잭션 안에서 실행 불가 → asyncpg가 자동 처리
            await conn.execute(f'CREATE DATABASE "{_TEST_DB_NAME}" OWNER {config.DB_USER}')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def initialize(request: FixtureRequest) -> Generator[None, None]:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # 안전망 1: dev DB와 test DB가 같으면 즉시 거절 (오설정 + 데이터 파괴 차단)
    if _TEST_DB_NAME == config.DB_NAME:
        raise RuntimeError(
            f"테스트 DB가 dev DB({config.DB_NAME})와 같습니다. "
            "TEST_DB_NAME 환경변수로 분리하거나 conftest의 기본값을 확인하세요."
        )
    # 안전망 2: 시작 전에 test DB 존재를 보장 (기존 컨테이너용 폴백)
    loop.run_until_complete(_ensure_test_database_exists_async())
    # db_url을 직접 전달하면 _TORTOISE_TEST_DB가 설정되어
    # TestCase도 PostgreSQL을 사용하게 된다.
    initializer(modules=TORTOISE_APP_MODELS, db_url=TEST_DB_URL)
    yield
    finalizer()
    loop.close()


@pytest_asyncio.fixture(autouse=True, scope="session")  # type: ignore[type-var]
def event_loop() -> None:
    pass
