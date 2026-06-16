"""관리자 액션 감사 로그 (CLAUDE.md §5 — PHI 책임 추적).

기록 대상:
- 사용자 정지/활성화/이메일 인증 강제/강제 탈퇴
- 챌린지 카탈로그 생성/수정/비활성화
- 공지 발송

기록 형식:
- admin_user_id : 관리자 ID
- action        : 액션 종류 enum
- target_type   : 대상 리소스 타입 (user/challenge/notification 등)
- target_id     : 대상 ID
- detail        : JSON 추가 정보 (변경 전/후 등)
- ip_address    : 관리자 IP (선택)
- created_at    : 자동
"""

from enum import StrEnum

from tortoise import fields, models


class AdminAction(StrEnum):
    USER_DEACTIVATE = "USER_DEACTIVATE"
    USER_ACTIVATE = "USER_ACTIVATE"
    USER_FORCE_VERIFY_EMAIL = "USER_FORCE_VERIFY_EMAIL"
    USER_FORCE_DELETE = "USER_FORCE_DELETE"
    CHALLENGE_CREATE = "CHALLENGE_CREATE"
    CHALLENGE_UPDATE = "CHALLENGE_UPDATE"
    CHALLENGE_DEACTIVATE = "CHALLENGE_DEACTIVATE"
    BROADCAST_SEND = "BROADCAST_SEND"
    SAFETY_EVENT_ACK = "SAFETY_EVENT_ACK"
    IMPERSONATE = "IMPERSONATE"


class TargetType(StrEnum):
    USER = "user"
    CHALLENGE = "challenge"
    NOTIFICATION = "notification"


class AdminActionLog(models.Model):
    id = fields.BigIntField(primary_key=True)
    admin_user = fields.ForeignKeyField("models.User", related_name="admin_action_logs", on_delete=fields.RESTRICT)
    action = fields.CharEnumField(enum_type=AdminAction, description="액션 종류")
    target_type = fields.CharEnumField(enum_type=TargetType, description="대상 리소스 타입")
    target_id = fields.BigIntField(description="대상 리소스 ID")
    detail = fields.JSONField(default=dict, description="추가 정보 (변경 전/후 값 등)")
    ip_address = fields.CharField(max_length=45, null=True, description="관리자 IP (선택)")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "admin_action_logs"
        indexes = [("admin_user_id", "created_at"), ("target_type", "target_id")]
        ordering = ["-created_at"]
