from datetime import date, datetime
from typing import Any

from pydantic import EmailStr

from app.core import config
from app.models.users import Gender, User

ALLOWED_UPDATE_FIELDS = ["name", "phone_number", "gender", "birthday"]
UPDATED_AT_FIELD = "updated_at"


class UserRepository:
    def __init__(self):
        self._model = User

    async def get_all(self):
        return await self._model.all()

    async def get_user(self, user_id: int) -> User | None:
        return await self._model.get_or_none(id=user_id)

    async def create_user(
        self,
        email: str | EmailStr,
        hashed_password: str,
        name: str,
        phone_number: str,
        gender: Gender,
        birthday: date,
        *,
        is_active: bool = True,
        is_admin: bool = False,
    ) -> User:
        return await self._model.create(
            email=email,
            hashed_password=hashed_password,
            name=name,
            phone_number=phone_number,
            gender=gender,
            birthday=birthday,
            is_active=is_active,
            is_admin=is_admin,
        )

    async def get_user_by_email(self, email: str) -> User | None:
        return await self._model.get_or_none(email=email)

    async def exists_by_email(self, email: str) -> bool:
        return await self._model.filter(email=email).exists()

    async def exists_by_phone_number(self, phone_number: str) -> bool:
        return await self._model.filter(phone_number=phone_number).exists()

    async def get_or_create_social_user(
        self,
        *,
        email: str,
        name: str,
        provider: str,
        provider_id: str,
    ) -> tuple[User, bool]:
        """소셜 로그인 유저를 이메일로 조회하거나 신규 생성. (created: bool) 반환."""
        user = await self._model.get_or_none(email=email)
        if user:
            return user, False
        user = await self._model.create(
            email=email,
            # 소셜 전용 계정은 비밀번호 로그인 불가 — bcrypt로 해석 불가능한 sentinel
            hashed_password=f"SOCIAL:{provider}:{provider_id}",
            name=name[:20],
            phone_number="00000000000",
            gender=Gender.MALE,
            birthday=date(2000, 1, 1),
            is_active=True,
            # REQ-AUTH-003: 소셜 로그인 계정은 별도 이메일 인증 불필요 (Kakao/Google이 검증)
            email_verified=True,
        )
        return user, True

    async def update_last_login(self, user_id: int) -> None:
        await self._model.filter(id=user_id).update(last_login=datetime.now(config.TIMEZONE))

    async def anonymize_and_deactivate(self, user: User) -> None:
        user.email = f"deleted_{user.id}@deleted.invalid"
        user.name = "탈퇴한 사용자"
        user.phone_number = "00000000000"
        user.hashed_password = "DELETED"
        user.is_active = False
        user.updated_at = datetime.now(config.TIMEZONE)
        await user.save(update_fields=["email", "name", "phone_number", "hashed_password", "is_active", "updated_at"])

    async def update_instance(self, user: User, data: dict[str, Any]) -> None:
        update_fields = []
        for key, value in data.items():
            if value is not None:
                setattr(user, key, value)
                update_fields.append(key)
        if update_fields:
            user.updated_at = datetime.now(config.TIMEZONE)
            update_fields.append(UPDATED_AT_FIELD)
            await user.save(update_fields=update_fields)
