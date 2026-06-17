from app.models.chat import ChatMessage, ChatRole, MessageFeedback


class ChatRepository:
    async def add(self, *, user_id: int, role: ChatRole, content: str) -> ChatMessage:
        return await ChatMessage.create(user_id=user_id, role=role, content=content)

    async def get_by_user(self, user_id: int, limit: int = 20, offset: int = 0) -> tuple[int, list[ChatMessage]]:
        qs = ChatMessage.filter(user_id=user_id)
        total = await qs.count()
        items = await qs.order_by("created_at").offset(offset).limit(limit)
        return total, items

    async def get_message(self, message_id: int) -> ChatMessage | None:
        return await ChatMessage.get_or_none(id=message_id)


class MessageFeedbackRepository:
    async def upsert(self, *, user_id: int, chat_message_id: int, rating: int, comment: str | None) -> MessageFeedback:
        """메시지+사용자당 1건 — 이미 있으면 갱신(재제출), 없으면 생성."""
        obj, _ = await MessageFeedback.update_or_create(
            user_id=user_id,
            chat_message_id=chat_message_id,
            defaults={"rating": rating, "comment": comment},
        )
        return obj
