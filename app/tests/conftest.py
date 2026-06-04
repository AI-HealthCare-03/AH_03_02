import asyncio
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
TEST_DB_URL = f"postgres://{config.DB_USER}:{config.DB_PASSWORD}@{_db_host}:{config.DB_PORT}/{config.DB_NAME}"


@pytest.fixture(scope="session", autouse=True)
def initialize(request: FixtureRequest) -> Generator[None, None]:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # db_url을 직접 전달하면 _TORTOISE_TEST_DB가 설정되어
    # TestCase도 PostgreSQL을 사용하게 된다.
    initializer(modules=TORTOISE_APP_MODELS, db_url=TEST_DB_URL)
    yield
    finalizer()
    loop.close()


@pytest_asyncio.fixture(autouse=True, scope="session")  # type: ignore[type-var]
def event_loop() -> None:
    pass
