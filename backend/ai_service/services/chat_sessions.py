from django.db.models import Count

from backend.ai_service.schemas.chat import (
    ChatMessageDetail,
    ChatSessionDetailResponse,
    ChatSessionSummary,
)
from backend.shared.django import ensure_django_setup


class ChatSessionNotFoundError(ValueError):
    pass


class ChatSessionReader:
    def list_sessions(self, *, user_id: int, limit: int = 50) -> list[ChatSessionSummary]:
        ensure_django_setup()

        from backend.django_app.core.models import ChatSession

        sessions = (
            ChatSession.objects.filter(user_id=user_id, is_active=True)
            .annotate(message_count=Count("messages"))
            .order_by("-updated_at", "-id")[:limit]
        )
        return [
            ChatSessionSummary(
                session_id=session.session_id,
                title=session.title,
                is_active=session.is_active,
                message_count=session.message_count,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
            for session in sessions
        ]

    def get_session(
        self,
        *,
        user_id: int,
        session_id: str,
        message_limit: int = 100,
    ) -> ChatSessionDetailResponse:
        ensure_django_setup()

        from backend.django_app.core.models import ChatSession

        session = (
            ChatSession.objects.filter(
                user_id=user_id,
                session_id=session_id,
                is_active=True,
            )
            .prefetch_related("messages")
            .first()
        )
        if not session:
            raise ChatSessionNotFoundError("Chat session was not found.")

        messages = session.messages.order_by("created_at", "id")[:message_limit]
        return ChatSessionDetailResponse(
            session_id=session.session_id,
            title=session.title,
            is_active=session.is_active,
            created_at=session.created_at,
            updated_at=session.updated_at,
            messages=[
                ChatMessageDetail(
                    id=message.id,
                    role=message.role,
                    content=message.content,
                    metadata=message.metadata,
                    created_at=message.created_at,
                )
                for message in messages
            ],
        )
