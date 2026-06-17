"""POST /api/v1/chat/messages 라우터 테스트.

패턴: tortoise.contrib.test.TestCase + httpx AsyncClient(ASGITransport)
인증: signup → login → Bearer 토큰 (기존 health_check / lifestyle_survey 테스트와 동일)
ChatService.ask: monkeypatch (Redis/worker 없이 라우터만 검증)
"""

from datetime import UTC, date, datetime

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.chat import ChatMessage, ChatRole, MessageFeedback
from app.models.users import User
from app.services import chat as chat_module

_SIGNUP_DATA = {
    "email": "chat_router_test@example.com",
    "password": "Password123!",
    "name": "챗라우터테스터",
    "gender": "MALE",
    "birth_date": "1990-01-01",
    "phone_number": "01055556666",
}
_LOGIN_DATA = {
    "email": "chat_router_test@example.com",
    "password": "Password123!",
}


async def _get_token(client: AsyncClient) -> str:
    """회원가입 후 access_token 반환 헬퍼."""
    await client.post("/api/v1/auth/signup", json=_SIGNUP_DATA)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN_DATA)
    return resp.json()["access_token"]


class TestChatRouterAuth(TestCase):
    async def test_post_message_requires_auth(self):
        """인증 없이 POST → 401."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/messages",
                json={"question": "인증 없이 질문"},
            )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestChatRouterAnswer(TestCase):
    async def test_post_message_returns_answer(self):
        """인증된 요청 + ChatService.ask monkeypatch → 200 + answer 반환."""
        from app.dtos.chat import ChatMessageResponse

        fake_answer = "하루 단백질 0.8 g/kg 권장합니다."
        fake_created_at = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)

        # ChatService.ask를 가짜 응답으로 교체 (Redis/worker 의존 없이)
        original_ask = chat_module.ChatService.ask

        async def fake_ask(self, user_id: int, question: str) -> ChatMessageResponse:  # noqa: ARG001
            return ChatMessageResponse(message_id=1, answer=fake_answer, created_at=fake_created_at)

        chat_module.ChatService.ask = fake_ask
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                token = await _get_token(client)
                response = await client.post(
                    "/api/v1/chat/messages",
                    json={"question": "단백질 권장량이 얼마인가요?"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            chat_module.ChatService.ask = original_ask

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["answer"] == fake_answer
        assert "created_at" in body
        assert body["message_id"] == 1  # 피드백 연결용 메시지 id 노출


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestChatFeedback(TestCase):
    """POST /api/v1/chat/messages/{id}/feedback — AI 답변 피드백 수집 (3-4)."""

    async def _setup_assistant_message(
        self, client: AsyncClient, *, role: ChatRole = ChatRole.ASSISTANT, content: str = "신장에 좋은 식이입니다."
    ) -> tuple[str, ChatMessage]:
        """로그인 토큰 + 그 사용자의 메시지(기본 어시스턴트)를 만들어 반환."""
        token = await _get_token(client)
        user = await User.get(email=_LOGIN_DATA["email"])
        msg = await ChatMessage.create(user_id=user.id, role=role, content=content)
        return token, msg

    async def test_feedback_requires_auth(self):
        """인증 없이 피드백 → 401."""
        async with _client() as client:
            response = await client.post("/api/v1/chat/messages/1/feedback", json={"rating": 1})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_feedback_success_and_upsert(self):
        """본인 어시스턴트 답변에 피드백 → 200, 재제출 시 upsert(1건 유지·rating 갱신)."""
        async with _client() as client:
            token, msg = await self._setup_assistant_message(client)
            auth = {"Authorization": f"Bearer {token}"}
            r1 = await client.post(
                f"/api/v1/chat/messages/{msg.id}/feedback",
                json={"rating": 1, "comment": "도움이 됐어요"},
                headers=auth,
            )
            assert r1.status_code == status.HTTP_200_OK
            assert r1.json()["rating"] == 1
            # 같은 답변에 재제출 → 갱신
            r2 = await client.post(f"/api/v1/chat/messages/{msg.id}/feedback", json={"rating": -1}, headers=auth)
            assert r2.status_code == status.HTTP_200_OK
            assert r2.json()["rating"] == -1
            assert await MessageFeedback.filter(chat_message_id=msg.id).count() == 1

    async def test_feedback_on_user_message_rejected(self):
        """사용자(USER) 메시지에는 피드백 불가 → 400."""
        async with _client() as client:
            token, msg = await self._setup_assistant_message(client, role=ChatRole.USER, content="질문입니다")
            auth = {"Authorization": f"Bearer {token}"}
            response = await client.post(f"/api/v1/chat/messages/{msg.id}/feedback", json={"rating": 1}, headers=auth)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_feedback_on_others_message_forbidden(self):
        """타인의 답변에는 피드백 불가 → 403."""
        async with _client() as client:
            token = await _get_token(client)
            other = await User.create(
                email="other_chat_user@example.com",
                hashed_password="$2b$12$dummy",
                name="타인",
                gender="MALE",
                birthday=date(1990, 1, 1),
                phone_number="01099998888",
            )
            msg = await ChatMessage.create(user_id=other.id, role=ChatRole.ASSISTANT, content="남의 답변")
            auth = {"Authorization": f"Bearer {token}"}
            response = await client.post(f"/api/v1/chat/messages/{msg.id}/feedback", json={"rating": 1}, headers=auth)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_feedback_missing_message_not_found(self):
        """존재하지 않는 메시지 → 404."""
        async with _client() as client:
            token = await _get_token(client)
            auth = {"Authorization": f"Bearer {token}"}
            response = await client.post("/api/v1/chat/messages/999999/feedback", json={"rating": 1}, headers=auth)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_feedback_invalid_rating(self):
        """rating 이 +1/-1 외 값이면 422 (Literal 검증)."""
        async with _client() as client:
            token, msg = await self._setup_assistant_message(client)
            auth = {"Authorization": f"Bearer {token}"}
            response = await client.post(f"/api/v1/chat/messages/{msg.id}/feedback", json={"rating": 5}, headers=auth)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
