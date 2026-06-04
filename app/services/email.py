"""이메일 발송 서비스 (Resend + Mock 토글).

EMAIL_MODE 환경변수로 동작 분기:
- demo: 외부 호출 없이 발송된 척만 함. 발송 코드는 응답에 직접 반환되어 시연 가능.
- production: Resend API로 실제 발송.

비고: 발표 시연 안정성을 위해 기본값은 demo. RESEND_API_KEY 미설정 시 production 모드도 demo로 강등.
"""

from dataclasses import dataclass
from typing import Literal

import resend
from fastapi import HTTPException
from starlette import status

from app.core import config

_DELIVERY_MODE = Literal["demo", "production"]


@dataclass
class EmailDeliveryResult:
    sent: bool
    mode: _DELIVERY_MODE
    demo_code: str | None = None
    message_id: str | None = None


class EmailService:
    """이메일 발송 추상화. 비밀번호 재설정 코드 전송용."""

    def __init__(self) -> None:
        self._mode: _DELIVERY_MODE = "production" if config.EMAIL_MODE == "production" else "demo"
        self._api_key = config.RESEND_API_KEY
        self._from = config.EMAIL_FROM

    @property
    def effective_mode(self) -> _DELIVERY_MODE:
        """실제 동작 모드. production이라도 키 없으면 demo로 강등."""
        if self._mode == "production" and not self._api_key:
            return "demo"
        return self._mode

    async def send_password_reset_code(self, to_email: str, code: str, expires_minutes: int = 5) -> EmailDeliveryResult:
        if self.effective_mode == "demo":
            return EmailDeliveryResult(sent=True, mode="demo", demo_code=code)

        try:
            resend.api_key = self._api_key
            params: resend.Emails.SendParams = {
                "from": self._from,
                "to": [to_email],
                "subject": "[CKD Care] 비밀번호 재설정 코드",
                "html": _render_password_reset_html(code, expires_minutes),
            }
            response = resend.Emails.send(params)
            message_id = response.get("id") if isinstance(response, dict) else None
            return EmailDeliveryResult(sent=True, mode="production", message_id=message_id)
        except Exception:
            # 외부 의존성 실패 시 발송 자체는 실패해도 사용자에게는 모호한 응답을 줘서
            # 계정 존재 여부를 노출하지 않는다. 단, 서버 로그에는 남길 수 있도록 예외 자체는 보존.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="이메일 발송 서비스를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
            ) from None

    async def send_email_verification_code(
        self, to_email: str, code: str, expires_hours: int = 24
    ) -> EmailDeliveryResult:
        """REQ-AUTH-003 회원가입 이메일 인증 6자리 코드 발송."""
        if self.effective_mode == "demo":
            return EmailDeliveryResult(sent=True, mode="demo", demo_code=code)

        try:
            resend.api_key = self._api_key
            params: resend.Emails.SendParams = {
                "from": self._from,
                "to": [to_email],
                "subject": "[CKD Care] 이메일 인증 코드",
                "html": _render_email_verification_html(code, expires_hours),
            }
            response = resend.Emails.send(params)
            message_id = response.get("id") if isinstance(response, dict) else None
            return EmailDeliveryResult(sent=True, mode="production", message_id=message_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="이메일 발송 서비스를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
            ) from None


def _render_password_reset_html(code: str, expires_minutes: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<body style="font-family: -apple-system, 'Noto Sans KR', sans-serif; background:#f8fafc; padding:32px;">
  <div style="max-width:520px; margin:0 auto; background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:32px;">
    <h2 style="margin:0 0 16px; color:#0f172a;">비밀번호 재설정 코드</h2>
    <p style="color:#475569; line-height:1.6;">아래 6자리 인증 코드를 앱에 입력하시면 임시 비밀번호가 발급됩니다.</p>
    <div style="margin:24px 0; padding:20px; background:#f1f5f9; border-radius:8px; text-align:center;">
      <p style="margin:0; font-size:32px; font-weight:bold; letter-spacing:8px; color:#0ea5e9;">{code}</p>
    </div>
    <p style="color:#94a3b8; font-size:13px; margin:0;">코드는 {expires_minutes}분 동안 유효하며, 본인이 요청하지 않았다면 이 메일을 무시하세요.</p>
    <hr style="border:none; border-top:1px solid #e2e8f0; margin:24px 0;" />
    <p style="color:#94a3b8; font-size:12px; margin:0;">CKD Care · 만성신부전 생활습관 챌린지</p>
  </div>
</body>
</html>"""


def _render_email_verification_html(code: str, expires_hours: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<body style="font-family: -apple-system, 'Noto Sans KR', sans-serif; background:#f8fafc; padding:32px;">
  <div style="max-width:520px; margin:0 auto; background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:32px;">
    <h2 style="margin:0 0 16px; color:#0f172a;">이메일 인증 코드</h2>
    <p style="color:#475569; line-height:1.6;">CKD Care에 가입해주셔서 감사합니다. 아래 6자리 인증 코드를 앱에 입력하시면 가입이 완료됩니다.</p>
    <div style="margin:24px 0; padding:20px; background:#f1f5f9; border-radius:8px; text-align:center;">
      <p style="margin:0; font-size:32px; font-weight:bold; letter-spacing:8px; color:#0ea5e9;">{code}</p>
    </div>
    <p style="color:#94a3b8; font-size:13px; margin:0;">코드는 {expires_hours}시간 동안 유효하며, 본인이 요청하지 않았다면 이 메일을 무시하세요.</p>
    <hr style="border:none; border-top:1px solid #e2e8f0; margin:24px 0;" />
    <p style="color:#94a3b8; font-size:12px; margin:0;">CKD Care · 만성신부전 생활습관 챌린지</p>
  </div>
</body>
</html>"""
