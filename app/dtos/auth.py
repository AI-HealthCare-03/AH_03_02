from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.validators import validate_birthday, validate_password, validate_phone_number
from app.models.users import Gender


class SignUpRequest(BaseModel):
    email: Annotated[
        EmailStr,
        Field(None, max_length=40),
    ]
    password: Annotated[str, Field(min_length=8), AfterValidator(validate_password)]
    name: Annotated[str, Field(max_length=20)]
    gender: Gender
    birth_date: Annotated[date, AfterValidator(validate_birthday)]
    phone_number: Annotated[str, AfterValidator(validate_phone_number)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=8)]


class LoginResponse(BaseModel):
    access_token: str


class TokenRefreshResponse(LoginResponse): ...


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    temp_password: str


class PasswordResetRequestBody(BaseModel):
    email: EmailStr


class PasswordResetRequestResponse(BaseModel):
    sent: bool
    mode: str
    demo_code: str | None = None
    expires_in_seconds: int


class PasswordResetVerifyBody(BaseModel):
    email: EmailStr
    code: Annotated[str, Field(min_length=6, max_length=6, pattern=r"^\d{6}$")]


class PasswordResetVerifyResponse(BaseModel):
    temp_password: str


# REQ-AUTH-003 이메일 인증 ----------------------------------------
class EmailVerificationRequestBody(BaseModel):
    email: EmailStr


class EmailVerificationRequestResponse(BaseModel):
    sent: bool
    mode: str  # demo | production
    demo_code: str | None = None
    expires_in_hours: int


class EmailVerificationVerifyBody(BaseModel):
    email: EmailStr
    code: Annotated[str, Field(min_length=6, max_length=6, pattern=r"^\d{6}$")]


class EmailVerificationVerifyResponse(BaseModel):
    verified: bool


class SignUpResponse(BaseModel):
    """REQ-AUTH-003: 회원가입 응답에 자동 발송된 인증 코드 정보 포함 (demo 모드에서 시연 안전)."""

    user_id: int
    email: EmailStr
    email_verification: EmailVerificationRequestResponse
