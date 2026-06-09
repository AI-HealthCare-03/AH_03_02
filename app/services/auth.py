import hashlib
import math
import secrets
import string
from datetime import UTC, datetime, timedelta

from fastapi.exceptions import HTTPException
from pydantic import EmailStr
from starlette import status
from tortoise.transactions import in_transaction

from app.core import config
from app.core.jwt.tokens import AccessToken, RefreshToken
from app.core.utils.common import normalize_phone_number
from app.core.utils.security import hash_password, verify_password
from app.dtos.auth import LoginRequest, SignUpRequest
from app.models.email_verification import EmailVerificationCode
from app.models.password_reset import PasswordResetCode
from app.models.users import User
from app.repositories.user_repository import UserRepository
from app.services.email import EmailDeliveryResult, EmailService
from app.services.jwt import JwtService

# REQ-AUTH-007 비밀번호 오류 잠금
MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 30

# REQ-AUTH-003 이메일 인증
EMAIL_VERIFICATION_TTL_HOURS = 24
EMAIL_VERIFICATION_MAX_ATTEMPTS = 5


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.jwt_service = JwtService()

    async def signup(self, data: SignUpRequest) -> User:
        from app.models.user_consent import ConsentType, UserConsent

        # 이메일 중복 체크
        await self.check_email_exists(data.email)

        # 입력받은 휴대폰 번호를 노말라이즈
        normalized_phone_number = normalize_phone_number(data.phone_number)

        # 휴대폰 번호 중복 체크
        await self.check_phone_number_exists(normalized_phone_number)

        # 필수 약관 동의 검증 — 신규 클라이언트가 consents를 보낸 경우에만 강제
        # (consents가 빈 리스트면 구 클라이언트로 간주, 검증 생략 → 백워드 호환)
        if data.consents:
            required = {ConsentType.TERMS_OF_SERVICE, ConsentType.PRIVACY_INFO, ConsentType.SENSITIVE_HEALTH}
            agreed_types = {c.consent_type for c in data.consents if c.agreed}
            missing = required - agreed_types
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="필수 약관(서비스 이용약관·개인정보 수집·민감의료정보)에 모두 동의해야 가입할 수 있습니다.",
                )

        # 유저 생성 + 동의 기록 (한 트랜잭션)
        async with in_transaction():
            user = await self.user_repo.create_user(
                email=data.email,
                hashed_password=hash_password(data.password),  # 해시화된 비밀번호를 사용
                name=data.name,
                phone_number=normalized_phone_number,
                gender=data.gender,
                birthday=data.birth_date,
            )

            for c in data.consents:
                await UserConsent.create(
                    user_id=user.id,
                    consent_type=c.consent_type,
                    version=c.version,
                    agreed=c.agreed,
                )

            return user

    async def authenticate(self, data: LoginRequest) -> User:
        # 이메일로 사용자 조회
        email = str(data.email)
        user = await self.user_repo.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="이메일 또는 비밀번호가 올바르지 않습니다."
            )

        # 비활성 계정 (탈퇴 등) 우선 차단
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="비활성화된 계정입니다.")

        # REQ-AUTH-003: 이메일 미인증 차단 (소셜 로그인 계정은 가입 시 True로 처리)
        if not user.email_verified and not user.hashed_password.startswith("SOCIAL:"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이메일 인증이 필요합니다. 가입 시 발송된 인증 코드로 인증을 완료해주세요.",
            )

        # REQ-AUTH-007: 잠금 상태 체크
        now = datetime.now(UTC)
        if user.locked_until and user.locked_until > now:
            remaining_seconds = (user.locked_until - now).total_seconds()
            remaining_minutes = math.ceil(remaining_seconds / 60)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"비밀번호 {MAX_FAILED_ATTEMPTS}회 이상 틀려 계정이 잠겼습니다. {remaining_minutes}분 후 다시 시도해주세요.",
            )

        # 비밀번호 검증
        if not verify_password(data.password, user.hashed_password):
            # 실패 카운터 +1
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
                # 5회 도달 — 30분 잠금 후 카운터 리셋
                user.locked_until = now + timedelta(minutes=LOCK_DURATION_MINUTES)
                user.failed_login_count = 0
                await user.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"비밀번호를 {MAX_FAILED_ATTEMPTS}회 틀렸습니다. {LOCK_DURATION_MINUTES}분 후 다시 시도해주세요.",
                )
            await user.save(update_fields=["failed_login_count", "updated_at"])
            remaining_attempts = MAX_FAILED_ATTEMPTS - user.failed_login_count
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"이메일 또는 비밀번호가 올바르지 않습니다. ({remaining_attempts}회 남음)",
            )

        # 비밀번호 성공 — 카운터·잠금 리셋
        if user.failed_login_count > 0 or user.locked_until is not None:
            user.failed_login_count = 0
            user.locked_until = None
            await user.save(update_fields=["failed_login_count", "locked_until", "updated_at"])

        return user

    async def login(self, user: User) -> dict[str, AccessToken | RefreshToken]:
        await self.user_repo.update_last_login(user.id)
        return self.jwt_service.issue_jwt_pair(user)

    async def check_email_exists(self, email: str | EmailStr) -> None:
        if await self.user_repo.exists_by_email(email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 이메일입니다.")

    async def check_phone_number_exists(self, phone_number: str) -> None:
        if await self.user_repo.exists_by_phone_number(phone_number):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 휴대폰 번호입니다.")

    async def issue_temp_password(self, email: str) -> str:
        user = await self.user_repo.get_user_by_email(email)
        if not user or not user.is_active:
            # 계정 존재 여부를 노출하지 않기 위해 동일한 응답
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 이메일이 없습니다.")
        if user.hashed_password.startswith("SOCIAL:"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="소셜 로그인 계정은 임시 비밀번호를 사용할 수 없습니다."
            )
        alphabet = string.ascii_letters + string.digits + "!@#$"
        temp_pw = "".join(secrets.choice(alphabet) for _ in range(12))
        await self.user_repo.update_instance(
            user=user,
            data={"hashed_password": hash_password(temp_pw), "token_version": user.token_version + 1},
        )
        return temp_pw

    async def request_password_reset(self, email: str) -> EmailDeliveryResult:
        """비밀번호 재설정 코드 발급 + 이메일 발송.

        보안:
        - 계정 존재 여부 노출 방지: 미가입·소셜 계정도 일반 응답을 반환할 수 있으나,
          현 UX는 명확한 안내를 우선하여 명시적 에러를 띄운다.
        - 코드는 SHA256 해시로만 저장 (평문 절대 보관 X).
        - 기존 미사용 코드는 무효화 (사용자당 활성 코드 1개).
        """
        user = await self.user_repo.get_user_by_email(email)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 이메일이 없습니다.")
        if user.hashed_password.startswith("SOCIAL:"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="소셜 로그인 계정은 비밀번호 재설정을 사용할 수 없습니다.",
            )

        # 사용자당 활성 코드 무효화 (used_at 셋팅)
        now = datetime.now(UTC)
        await PasswordResetCode.filter(user_id=user.id, used_at__isnull=True, expires_at__gt=now).update(used_at=now)

        # 새 코드 발급 (6자리 숫자)
        code = f"{secrets.randbelow(1_000_000):06d}"
        ttl = config.PASSWORD_RESET_CODE_TTL_SECONDS
        await PasswordResetCode.create(
            user_id=user.id,
            code_hash=_hash_code(code),
            expires_at=now + timedelta(seconds=ttl),
        )

        # 이메일 발송 (demo 모드면 응답에 코드 포함)
        email_service = EmailService()
        return await email_service.send_password_reset_code(to_email=email, code=code, expires_minutes=ttl // 60)

    async def verify_password_reset(self, email: str, code: str) -> str:
        """코드 검증 + 임시 비밀번호 발급. 성공 시 임시 비밀번호 평문 반환.

        실패 시 attempts 증가, 5회 초과 시 코드 무효화.
        """
        user = await self.user_repo.get_user_by_email(email)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 이메일이 없습니다.")

        now = datetime.now(UTC)
        record = (
            await PasswordResetCode.filter(user_id=user.id, used_at__isnull=True, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="발급된 인증 코드가 없거나 만료되었습니다. 코드를 다시 요청해주세요.",
            )

        if record.attempts >= config.PASSWORD_RESET_MAX_ATTEMPTS:
            record.used_at = now
            await record.save(update_fields=["used_at"])
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="인증 시도 횟수를 초과했습니다. 코드를 다시 요청해주세요.",
            )

        if record.code_hash != _hash_code(code):
            record.attempts += 1
            await record.save(update_fields=["attempts"])
            remaining = config.PASSWORD_RESET_MAX_ATTEMPTS - record.attempts
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"인증 코드가 일치하지 않습니다. ({remaining}회 남음)",
            )

        # 검증 성공 — 코드 소비 + 임시 비밀번호 발급
        record.used_at = now
        await record.save(update_fields=["used_at"])

        alphabet = string.ascii_letters + string.digits + "!@#$"
        temp_pw = "".join(secrets.choice(alphabet) for _ in range(12))
        await self.user_repo.update_instance(
            user=user,
            data={"hashed_password": hash_password(temp_pw), "token_version": user.token_version + 1},
        )
        # 로그인 잠금 상태가 있으면 초기화 (정상 사용 흐름 복귀)
        if user.failed_login_count > 0 or user.locked_until is not None:
            user.failed_login_count = 0
            user.locked_until = None
            await user.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
        return temp_pw

    async def request_email_verification(self, user_id: int) -> EmailDeliveryResult:
        """REQ-AUTH-003 이메일 인증 6자리 코드 발급·발송.

        기존 사용자당 활성 코드는 무효화하고 새 코드 1개만 활성 상태로 유지.
        이미 인증 완료된 경우 400 반환.
        """
        user = await User.get_or_none(id=user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 계정이 없습니다.")
        if user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 인증이 완료된 계정입니다.",
            )
        if user.hashed_password.startswith("SOCIAL:"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="소셜 로그인 계정은 별도 이메일 인증이 필요하지 않습니다.",
            )

        now = datetime.now(UTC)
        await EmailVerificationCode.filter(user_id=user.id, used_at__isnull=True, expires_at__gt=now).update(
            used_at=now
        )

        code = f"{secrets.randbelow(1_000_000):06d}"
        await EmailVerificationCode.create(
            user_id=user.id,
            code_hash=_hash_code(code),
            expires_at=now + timedelta(hours=EMAIL_VERIFICATION_TTL_HOURS),
        )

        email_service = EmailService()
        return await email_service.send_email_verification_code(
            to_email=user.email, code=code, expires_hours=EMAIL_VERIFICATION_TTL_HOURS
        )

    async def verify_email_code(self, user_id: int, code: str) -> None:
        """REQ-AUTH-003 코드 검증 + email_verified 갱신.

        실패 시 attempts +1, 5회 초과 시 코드 무효화.
        """
        user = await User.get_or_none(id=user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 계정이 없습니다.")
        if user.email_verified:
            return  # 이미 인증 완료 — idempotent

        now = datetime.now(UTC)
        record = (
            await EmailVerificationCode.filter(user_id=user.id, used_at__isnull=True, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="발급된 인증 코드가 없거나 만료되었습니다. 코드를 다시 요청해주세요.",
            )

        if record.attempts >= EMAIL_VERIFICATION_MAX_ATTEMPTS:
            record.used_at = now
            await record.save(update_fields=["used_at"])
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="인증 시도 횟수를 초과했습니다. 코드를 다시 요청해주세요.",
            )

        if record.code_hash != _hash_code(code):
            record.attempts += 1
            await record.save(update_fields=["attempts"])
            remaining = EMAIL_VERIFICATION_MAX_ATTEMPTS - record.attempts
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"인증 코드가 일치하지 않습니다. ({remaining}회 남음)",
            )

        # 검증 성공 — 코드 소비 + email_verified True
        record.used_at = now
        await record.save(update_fields=["used_at"])
        user.email_verified = True
        await user.save(update_fields=["email_verified", "updated_at"])
