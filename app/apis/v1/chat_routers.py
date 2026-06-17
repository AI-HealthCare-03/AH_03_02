from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import ORJSONResponse as Response
from fastapi.responses import StreamingResponse

from app.core.rate_limit import limiter
from app.dependencies.security import get_request_user
from app.dtos.chat import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    MessageFeedbackRequest,
    MessageFeedbackResponse,
)
from app.models.users import User
from app.services.chat import ChatService

chat_router = APIRouter(prefix="/chat", tags=["chat"])


@chat_router.post(
    "/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="RAG 챗봇에 질문",
)
@limiter.limit("10/minute")
async def create_message(
    request: Request,
    body: ChatMessageCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChatService, Depends(ChatService)],
) -> Response:
    result = await service.ask(user_id=user.id, question=body.question)
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)


@chat_router.post("/messages/stream", summary="RAG 챗봇 질문 (SSE 토큰 스트리밍)")
@limiter.limit("10/minute")
async def create_message_stream(
    request: Request,
    body: ChatMessageCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChatService, Depends(ChatService)],
) -> StreamingResponse:
    return StreamingResponse(
        service.ask_stream(user_id=user.id, question=body.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@chat_router.post(
    "/messages/{message_id}/feedback",
    response_model=MessageFeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="AI 답변에 대한 사용자 피드백(도움됨/안됨) 제출",
)
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    message_id: int,
    body: MessageFeedbackRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChatService, Depends(ChatService)],
) -> Response:
    result = await service.submit_feedback(
        user_id=user.id, message_id=message_id, rating=body.rating, comment=body.comment
    )
    return Response(result.model_dump(), status_code=status.HTTP_200_OK)
