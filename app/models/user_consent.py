"""회원가입 시 동의 기록 (개인정보보호법 §22, §23, §22의2).

UserConsent는 사용자 × 약관 종류 × 버전 단위로 동의 시각을 영구 기록한다.
- 약관 본문은 docs/legal/consent-texts.md 또는 코드 상수로 관리하며,
  내용이 바뀌면 version을 올린 새 row를 추가한다 (기존 row는 그대로 둠).
- 회원 탈퇴 시 본인의 개인정보 처리방침에 따라 anonymize·delete 처리하되,
  법적 분쟁 보존 기간(예: 전자상거래 분쟁 3년) 동안은 보존할 수 있다.
"""

from enum import StrEnum

from tortoise import fields, models


class ConsentType(StrEnum):
    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"  # 서비스 이용약관 (필수)
    PRIVACY_INFO = "PRIVACY_INFO"  # 개인정보 수집 및 이용 동의 (필수)
    SENSITIVE_HEALTH = "SENSITIVE_HEALTH"  # 민감의료정보 수집·이용 동의 (필수, §23)
    MARKETING = "MARKETING"  # 마케팅 수신 동의 (선택)


class UserConsent(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="consents")
    consent_type = fields.CharEnumField(enum_type=ConsentType)
    version = fields.CharField(max_length=20, description="약관 본문 버전 (예: v1)")
    agreed = fields.BooleanField(description="동의=True / 거부=False. 필수 항목 거부는 가입 자체가 막힘")
    agreed_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_consents"
        unique_together = [("user", "consent_type", "version")]
        indexes = [("user_id", "consent_type")]
