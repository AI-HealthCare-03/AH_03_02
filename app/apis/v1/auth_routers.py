import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse as Response

from app.core import config
from app.core.config import Env
from app.core.rate_limit import limiter
from app.dtos.auth import (
    EmailVerificationRequestBody,
    EmailVerificationRequestResponse,
    EmailVerificationVerifyBody,
    EmailVerificationVerifyResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    PasswordResetRequestBody,
    PasswordResetRequestResponse,
    PasswordResetVerifyBody,
    PasswordResetVerifyResponse,
    SignUpRequest,
    SignUpResponse,
    TokenRefreshResponse,
)
from app.repositories.user_repository import UserRepository
from app.services.auth import EMAIL_VERIFICATION_TTL_HOURS, AuthService
from app.services.charge_mode import ChargeModeService
from app.services.jwt import JwtService
from app.services.points import PointService
from app.services.streak_protect import StreakProtectService

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# 이메일 형식 검증용 정규식 (Pydantic EmailStr보다 가벼움 — 폼 입력 사전 체크에 충분)
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@auth_router.get(
    "/check-email",
    status_code=status.HTTP_200_OK,
    summary="이메일 중복 확인 (회원가입 사전 체크)",
    description="입력한 이메일이 가입 가능한지 확인. 형식 검증 + DB 중복 확인.",
)
@limiter.limit("20/minute")
async def check_email(
    request: Request,
    email: str,
    user_repo: Annotated[UserRepository, Depends(UserRepository)],
) -> Response:
    """이메일 형식이 잘못되면 400, 사용 중이면 available=false, 가능하면 available=true 반환.

    회원가입 폼에서 이메일 입력 후 사용자가 "중복 확인" 버튼 누를 때 호출.
    `signup` 라우트도 중복을 체크하지만, UX상 가입 시도 전 미리 알려주는 용도.
    """
    if not _EMAIL_PATTERN.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="입력하신 이메일 형식이 올바르지 않습니다.",
        )
    taken = await user_repo.exists_by_email(email)
    return Response(
        content={"available": not taken, "email": email},
        status_code=status.HTTP_200_OK,
    )


@auth_router.post("/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def signup(
    request: Request,
    body: SignUpRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    """REQ-AUTH-003: 회원가입 직후 자동으로 이메일 인증 코드 발송.

    demo 모드면 응답에 코드가 포함돼 시연 안전. production 모드면 demo_code=null.
    """
    user = await auth_service.signup(body)
    delivery = await auth_service.request_email_verification(user.id)
    return Response(
        content={
            "user_id": user.id,
            "email": user.email,
            "email_verification": {
                "sent": delivery.sent,
                "mode": delivery.mode,
                "demo_code": delivery.demo_code,
                "expires_in_hours": EMAIL_VERIFICATION_TTL_HOURS,
            },
        },
        status_code=status.HTTP_201_CREATED,
    )


@auth_router.post(
    "/email-verification/request",
    response_model=EmailVerificationRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="REQ-AUTH-003 이메일 인증 코드 재발송",
)
@limiter.limit("3/hour")
async def email_verification_request(
    request: Request,
    body: EmailVerificationRequestBody,
    auth_service: Annotated[AuthService, Depends(AuthService)],
    user_repo: Annotated[UserRepository, Depends(UserRepository)],
) -> Response:
    """이메일 기준 인증 코드 재발송. 1시간 3회 제한 (명세 v0.8 REQ-AUTH-003)."""
    user = await user_repo.get_user_by_email(str(body.email))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 이메일이 없습니다.")
    delivery = await auth_service.request_email_verification(user.id)
    return Response(
        content={
            "sent": delivery.sent,
            "mode": delivery.mode,
            "demo_code": delivery.demo_code,
            "expires_in_hours": EMAIL_VERIFICATION_TTL_HOURS,
        },
        status_code=status.HTTP_200_OK,
    )


@auth_router.post(
    "/email-verification/verify",
    response_model=EmailVerificationVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="REQ-AUTH-003 이메일 인증 코드 검증",
)
@limiter.limit("10/minute")
async def email_verification_verify(
    request: Request,
    body: EmailVerificationVerifyBody,
    auth_service: Annotated[AuthService, Depends(AuthService)],
    user_repo: Annotated[UserRepository, Depends(UserRepository)],
) -> Response:
    user = await user_repo.get_user_by_email(str(body.email))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 이메일이 없습니다.")
    await auth_service.verify_email_code(user.id, body.code)
    return Response(content={"verified": True}, status_code=status.HTTP_200_OK)


@auth_router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
    point_service: Annotated[PointService, Depends(PointService)],
) -> Response:
    user = await auth_service.authenticate(body)
    tokens = await auth_service.login(user)
    today = date.today()
    # 일일 로그인 보상 (당일 첫 로그인 시 +10)
    await point_service.award_login(user.id, today)
    # 스트릭 보호권 자동 소모 평가 (어제 체크인 0회 + 보호권 보유 시)
    await StreakProtectService().evaluate(user.id, today)
    # 충전 모드 평가 (진입/경고 알림 트리거)
    await ChargeModeService().evaluate(user.id, today)
    resp = Response(
        content=LoginResponse(access_token=str(tokens["access_token"])).model_dump(), status_code=status.HTTP_200_OK
    )
    resp.set_cookie(
        key="refresh_token",
        value=str(tokens["refresh_token"]),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        samesite="lax",
        domain=config.COOKIE_DOMAIN or None,
        # 쿠키 만료를 refresh 토큰 수명과 일치 (이전: access exp(15분)를 잘못 사용 → SEC-2). max_age는 초 단위
        max_age=config.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )
    return resp


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> Response:
    resp = Response(content=None, status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(key="refresh_token")
    return resp


@auth_router.get("/token/refresh", response_model=TokenRefreshResponse, status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def token_refresh(
    request: Request,
    jwt_service: Annotated[JwtService, Depends(JwtService)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing.")
    access_token = await jwt_service.refresh_jwt(refresh_token)
    return Response(
        content=TokenRefreshResponse(access_token=str(access_token)).model_dump(), status_code=status.HTTP_200_OK
    )


@auth_router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="임시 비밀번호 발급 (즉시·구버전)",
    description="이메일로 임시 비밀번호를 즉시 발급합니다. 발급 즉시 기존 비밀번호는 무효화됩니다.",
    deprecated=True,
)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    temp_pw = await auth_service.issue_temp_password(email=str(body.email))
    return Response(content=ForgotPasswordResponse(temp_password=temp_pw).model_dump(), status_code=status.HTTP_200_OK)


@auth_router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="비밀번호 재설정 코드 요청",
    description=(
        "이메일로 6자리 인증 코드를 발송합니다 (TTL 5분). EMAIL_MODE=demo일 경우 응답에 코드를 직접 반환합니다(시연용)."
    ),
)
@limiter.limit("5/minute")
async def request_password_reset(
    request: Request,
    body: PasswordResetRequestBody,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    result = await auth_service.request_password_reset(email=str(body.email))
    return Response(
        content=PasswordResetRequestResponse(
            sent=result.sent,
            mode=result.mode,
            demo_code=result.demo_code,
            expires_in_seconds=config.PASSWORD_RESET_CODE_TTL_SECONDS,
        ).model_dump(),
        status_code=status.HTTP_200_OK,
    )


@auth_router.post(
    "/password-reset/verify",
    response_model=PasswordResetVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="비밀번호 재설정 코드 검증 + 임시 비밀번호 발급",
    description="6자리 코드 검증 후 임시 비밀번호를 발급합니다. 검증 실패 5회 초과 시 코드 무효화.",
)
@limiter.limit("10/minute")
async def verify_password_reset(
    request: Request,
    body: PasswordResetVerifyBody,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    temp_pw = await auth_service.verify_password_reset(email=str(body.email), code=body.code)
    return Response(
        content=PasswordResetVerifyResponse(temp_password=temp_pw).model_dump(),
        status_code=status.HTTP_200_OK,
    )
