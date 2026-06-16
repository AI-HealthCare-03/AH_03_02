from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.users import User
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService

security = HTTPBearer()

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def get_request_user(
    request: Request,
    credential: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    token = credential.credentials
    verified = JwtService().verify_jwt(token=token, token_type="access")
    # 읽기전용 임퍼소네이션(view-as) 토큰: 쓰기 메서드 차단(서버 강제).
    if verified.payload.get("readonly") and request.method in _WRITE_METHODS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="읽기전용 임퍼소네이션 세션에서는 데이터를 변경할 수 없습니다.",
        )
    user_id = verified.payload["user_id"]
    user = await UserRepository().get_user(user_id)
    if not user:
        raise HTTPException(detail="Authenticate Failed.", status_code=status.HTTP_401_UNAUTHORIZED)
    return user


async def get_admin_user(user: Annotated[User, Depends(get_request_user)]) -> User:
    """관리자 전용 엔드포인트 가드 (User.is_admin=True 필수)."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return user
