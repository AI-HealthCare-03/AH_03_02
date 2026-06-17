"""REQ-NF-008 / REQ-SEC-004 — API Rate Limiting (slowapi).

정책:
- 로그인·비밀번호 재설정 등 인증 액션: 5회/분
- 일반 GET·POST: 60회/분 (글로벌 기본값)
- 키 함수: 클라이언트 IP

발표 시연용은 인메모리 백엔드. 운영 시 Redis 백엔드로 전환 권장.

RATE_LIMIT_ENABLED=false 일 때는 모든 제한이 no-op (단일 IP 부하테스트 등 측정용).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core import config

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    enabled=config.RATE_LIMIT_ENABLED,  # 부하테스트(단일 IP) 시 false 로 비활성화
)
