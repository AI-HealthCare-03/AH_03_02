from enum import StrEnum

from tortoise import fields, models


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="chat_messages")
    role = fields.CharEnumField(enum_type=ChatRole, description="발화 주체 (user/assistant)")
    content = fields.TextField(description="질문 또는 답변 본문")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_messages"
        ordering = ["created_at"]


class MessageFeedback(models.Model):
    """AI 답변 품질에 대한 사용자 피드백 (3-4 피드백 수집 루프).

    어시스턴트 메시지 1건 + 사용자 1명당 1개(unique). 재제출 시 upsert로 갱신.
    rating: +1(도움됨) / -1(도움 안 됨). 부정 피드백 누적 답변을 추후 품질 개선·재학습에 활용.
    """

    id = fields.BigIntField(primary_key=True)
    chat_message = fields.ForeignKeyField("models.ChatMessage", related_name="feedbacks", on_delete=fields.CASCADE)
    user = fields.ForeignKeyField("models.User", related_name="message_feedbacks")
    rating = fields.SmallIntField(description="+1 도움됨 / -1 도움 안 됨")
    comment = fields.TextField(null=True, description="선택적 사유 (예: 부정확함·이해 어려움)")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "message_feedbacks"
        unique_together = (("chat_message", "user"),)
        ordering = ["-created_at"]
