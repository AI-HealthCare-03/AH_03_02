from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.validators import optional_after_validator, validate_birthday, validate_password, validate_phone_number
from app.dtos.base import BaseSerializerModel
from app.models.users import Gender


class UserUpdateRequest(BaseModel):
    name: Annotated[str | None, Field(None, min_length=2, max_length=20)]
    email: Annotated[
        EmailStr | None,
        Field(None, max_length=40),
    ]
    phone_number: Annotated[
        str | None,
        Field(None, description="Available Format: +8201011112222, 01011112222, 010-1111-2222"),
        optional_after_validator(validate_phone_number),
    ]
    birthday: Annotated[
        date | None,
        Field(None, description="Date Format: YYYY-MM-DD"),
        optional_after_validator(validate_birthday),
    ]
    gender: Annotated[
        Gender | None,
        Field(None, description="'MALE' or 'FEMALE'"),
    ]


class PasswordChangeRequest(BaseModel):
    current_password: Annotated[str, Field(min_length=8)]
    new_password: Annotated[str, Field(min_length=8), AfterValidator(validate_password)]


class UserInfoResponse(BaseSerializerModel):
    id: int
    name: str
    email: str
    phone_number: str
    birthday: date
    gender: Gender
    is_admin: bool = False
    created_at: datetime
