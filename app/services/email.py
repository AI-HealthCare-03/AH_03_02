"""이메일 발송 서비스 (Resend / Gmail SMTP / Mock 토글).

EMAIL_MODE 환경변수로 동작 분기:
- demo       : 외부 호출 없이 발송된 척만 함. 발송 코드는 응답에 직접 반환되어 시연 가능.
- gmail      : Gmail SMTP(`smtp.gmail.com:587`)로 실제 발송. 동시에 응답에도 코드를 포함시켜
               시연 fallback으로 동작 (스팸함 분류·메일 지연 대비). SMTP_USERNAME/PASSWORD
               미설정 시 demo로 자동 강등.
- production : Resend API로 실제 발송. 응답 코드 null. RESEND_API_KEY 미설정 시 demo로 강등.

비고: 발표 시연 안정성을 위해 기본값은 demo. gmail 모드는 외부 발송이 필요한 시연/베타 운영에서
사용. production 전환은 본인 도메인 SPF/DKIM 인증 후 권장.
"""

from dataclasses import dataclass
from email.message import EmailMessage
from typing import Literal

import aiosmtplib
import resend
from fastapi import HTTPException
from starlette import status

from app.core import config

_DELIVERY_MODE = Literal["demo", "gmail", "production"]


@dataclass
class EmailDeliveryResult:
    sent: bool
    mode: _DELIVERY_MODE
    demo_code: str | None = None
    message_id: str | None = None


class EmailService:
    """이메일 발송 추상화. 회원가입 인증 + 비밀번호 재설정 코드 전송용."""

    def __init__(self) -> None:
        raw_mode = (config.EMAIL_MODE or "demo").lower()
        if raw_mode not in ("demo", "gmail", "production"):
            raw_mode = "demo"
        self._mode: _DELIVERY_MODE = raw_mode  # type: ignore[assignment]
        self._api_key = config.RESEND_API_KEY
        self._from = config.EMAIL_FROM
        self._smtp_host = config.SMTP_HOST
        self._smtp_port = config.SMTP_PORT
        self._smtp_user = config.SMTP_USERNAME
        self._smtp_pass = config.SMTP_PASSWORD

    @property
    def effective_mode(self) -> _DELIVERY_MODE:
        """실제 동작 모드. 인증 정보 누락 시 demo로 강등."""
        if self._mode == "production" and not self._api_key:
            return "demo"
        if self._mode == "gmail" and (not self._smtp_user or not self._smtp_pass):
            return "demo"
        return self._mode

    async def send_password_reset_code(self, to_email: str, code: str, expires_minutes: int = 5) -> EmailDeliveryResult:
        return await self._send(
            to_email=to_email,
            code=code,
            subject="[CKD Care] 비밀번호 재설정 코드",
            html=_render_password_reset_html(code, expires_minutes),
            text=_render_password_reset_text(code, expires_minutes),
        )

    async def send_email_verification_code(
        self, to_email: str, code: str, expires_hours: int = 24
    ) -> EmailDeliveryResult:
        """REQ-AUTH-003 회원가입 이메일 인증 6자리 코드 발송."""
        return await self._send(
            to_email=to_email,
            code=code,
            subject="[CKD Care] 이메일 인증 코드",
            html=_render_email_verification_html(code, expires_hours),
            text=_render_email_verification_text(code, expires_hours),
        )

    # ────────────────────────────────────────────────────────────
    # 내부 발송 분기
    # ────────────────────────────────────────────────────────────
    async def _send(self, *, to_email: str, code: str, subject: str, html: str, text: str) -> EmailDeliveryResult:
        mode = self.effective_mode
        if mode == "demo":
            return EmailDeliveryResult(sent=True, mode="demo", demo_code=code)
        if mode == "gmail":
            message_id = await self._send_via_smtp(to_email=to_email, subject=subject, html=html, text=text)
            # gmail 모드는 시연 fallback 유지 — 응답에도 코드 포함 (스팸함/지연 대비)
            return EmailDeliveryResult(sent=True, mode="gmail", demo_code=code, message_id=message_id)
        # production
        return EmailDeliveryResult(
            sent=True,
            mode="production",
            message_id=self._send_via_resend(to_email=to_email, subject=subject, html=html),
        )

    def _send_via_resend(self, *, to_email: str, subject: str, html: str) -> str | None:
        try:
            resend.api_key = self._api_key
            params: resend.Emails.SendParams = {
                "from": self._from,
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
            response = resend.Emails.send(params)
            return response.get("id") if isinstance(response, dict) else None
        except Exception:
            # 외부 의존성 실패 시 발송 자체는 실패해도 사용자에게는 모호한 응답을 줘서
            # 계정 존재 여부를 노출하지 않는다. 단, 서버 로그에는 남길 수 있도록 예외 자체는 보존.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="이메일 발송 서비스를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
            ) from None

    async def _send_via_smtp(self, *, to_email: str, subject: str, html: str, text: str) -> str | None:
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Reply-To"] = self._smtp_user  # 응답은 발신 Gmail로
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")

        try:
            await aiosmtplib.send(
                msg,
                hostname=self._smtp_host,
                port=self._smtp_port,
                username=self._smtp_user,
                password=self._smtp_pass,
                start_tls=True,
                timeout=20,
            )
            return None  # aiosmtplib는 message-id 직접 반환 X. Gmail이 자동 부여
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="이메일 발송 서비스를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
            ) from None


# ────────────────────────────────────────────────────────────
# HTML / 텍스트 템플릿
# ────────────────────────────────────────────────────────────
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


def _render_password_reset_text(code: str, expires_minutes: int) -> str:
    return (
        "[CKD Care] 비밀번호 재설정 코드\n\n"
        f"인증 코드: {code}\n"
        f"코드는 {expires_minutes}분 동안 유효합니다.\n\n"
        "본인이 요청하지 않았다면 이 메일을 무시하세요."
    )


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


def _render_email_verification_text(code: str, expires_hours: int) -> str:
    return (
        "[CKD Care] 이메일 인증 코드\n\n"
        f"인증 코드: {code}\n"
        f"코드는 {expires_hours}시간 동안 유효합니다.\n\n"
        "본인이 요청하지 않았다면 이 메일을 무시하세요."
    )
