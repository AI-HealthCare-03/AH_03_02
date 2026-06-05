from enum import StrEnum

from tortoise import fields, models


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class User(models.Model):
    id = fields.BigIntField(primary_key=True)
    email = fields.CharField(max_length=40, unique=True)
    hashed_password = fields.CharField(max_length=128)
    name = fields.CharField(max_length=20)
    gender = fields.CharEnumField(enum_type=Gender)
    birthday = fields.DateField()
    phone_number = fields.CharField(max_length=11, unique=True)
    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    active_skin_code = fields.CharField(max_length=20, null=True, description="현재 장착한 스킨 ItemCode (null=기본)")
    # REQ-AUTH-007 비밀번호 오류 잠금
    failed_login_count = fields.IntField(default=0, description="연속 비밀번호 실패 횟수")
    locked_until = fields.DatetimeField(null=True, description="계정 잠금 해제 시각 (null=미잠금)")
    # REQ-AUTH-003 회원가입 이메일 인증
    email_verified = fields.BooleanField(default=False, description="이메일 인증 완료 여부 (소셜 로그인은 True 유지)")
    # REQ-SEC: JWT 무효화 버전 — 비밀번호 변경/재설정 시 증가시켜 기존 refresh 토큰을 일괄 무효화
    token_version = fields.IntField(default=0, description="토큰 무효화 버전 (refresh 검증 시 대조)")
    # 챌린지 숙련도 (1=입문/잔디, 2=초보/산스장, 3=중급/헬스장, 4=숙련/지옥). EggWidget 배경 결정용.
    proficiency = fields.IntField(default=1, description="챌린지 숙련도 1~4 (1=입문, 4=숙련)")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"
