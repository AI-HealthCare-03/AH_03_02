from tortoise import fields, models


class EmailVerificationCode(models.Model):
    """REQ-AUTH-003 회원가입 이메일 인증 6자리 코드.

    PasswordResetCode와 동일 패턴 — SHA256 해시 저장, 24h TTL, 5회 시도 제한, 일회용.
    """

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="email_verification_codes", on_delete=fields.CASCADE)
    code_hash = fields.CharField(max_length=64, description="SHA256 해시 (코드 평문 저장 금지)")
    expires_at = fields.DatetimeField(description="만료 시각 (UTC)")
    attempts = fields.IntField(default=0, description="검증 시도 횟수 (5회 초과 시 무효)")
    used_at = fields.DatetimeField(null=True, description="성공 사용 시각 (이후 재사용 불가)")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "email_verification_codes"
        indexes = [("user_id", "expires_at")]
