from django.db.models import Count

from backend.ai_service.schemas.chat import (
    ChatMessageDetail,
    ChatSessionArchiveResponse,
    ChatSessionDetailResponse,
    ChatSessionRenameResponse,
    ChatSessionSummary,
)
from backend.shared.django import ensure_django_setup


class ChatSessionNotFoundError(ValueError):
    pass


class ChatSessionReader:
    def list_sessions(
        self,
        *,
        user_id: int,
        can_view_all: bool = False,
        limit: int = 50,
    ) -> list[ChatSessionSummary]:
        ensure_django_setup()

        from django.db import close_old_connections

        from backend.django_app.core.models import ChatSession

        close_old_connections()
        try:
            filters = {"is_active": True}
            if not can_view_all:
                filters["user_id"] = user_id

            sessions = (
                ChatSession.objects.filter(**filters)
                .select_related("user")
                .annotate(message_count=Count("messages"))
                .order_by("-updated_at", "-id")[:limit]
            )
            return [
                ChatSessionSummary(
                    session_id=session.session_id,
                    user_id=session.user_id,
                    username=session.user.username,
                    title=session.title,
                    is_active=session.is_active,
                    message_count=session.message_count,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                )
                for session in sessions
            ]
        finally:
            close_old_connections()

    def get_session(
        self,
        *,
        user_id: int,
        session_id: str,
        can_view_all: bool = False,
        message_limit: int = 100,
    ) -> ChatSessionDetailResponse:
        ensure_django_setup()

        from django.db import close_old_connections

        from backend.django_app.core.models import ChatSession

        close_old_connections()
        try:
            filters = {
                "session_id": session_id,
                "is_active": True,
            }
            if not can_view_all:
                filters["user_id"] = user_id

            session = (
                ChatSession.objects.filter(**filters)
                .select_related("user")
                .prefetch_related("messages")
                .first()
            )
            if not session:
                raise ChatSessionNotFoundError("Chat session was not found.")

            messages = session.messages.order_by("created_at", "id")[:message_limit]
            return ChatSessionDetailResponse(
                session_id=session.session_id,
                user_id=session.user_id,
                username=session.user.username,
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
        finally:
            close_old_connections()

    def archive_session(self, *, user_id: int, session_id: str) -> ChatSessionArchiveResponse:
        ensure_django_setup()

        from django.db import close_old_connections

        from backend.django_app.core.models import ChatSession

        close_old_connections()
        try:
            session = ChatSession.objects.filter(
                user_id=user_id,
                session_id=session_id,
                is_active=True,
            ).first()
            if not session:
                raise ChatSessionNotFoundError("Chat session was not found.")

            session.is_active = False
            session.save(update_fields=["is_active", "updated_at"])
            return ChatSessionArchiveResponse(
                session_id=session.session_id,
                archived=True,
                is_active=session.is_active,
            )
        finally:
            close_old_connections()

    def rename_session(
        self,
        *,
        user_id: int,
        session_id: str,
        title: str,
    ) -> ChatSessionRenameResponse:
        ensure_django_setup()

        from django.db import close_old_connections

        from backend.django_app.core.models import ChatSession

        close_old_connections()
        try:
            session = ChatSession.objects.filter(
                user_id=user_id,
                session_id=session_id,
                is_active=True,
            ).first()
            if not session:
                raise ChatSessionNotFoundError("Chat session was not found.")

            session.title = title.strip()
            session.save(update_fields=["title", "updated_at"])
            return ChatSessionRenameResponse(
                session_id=session.session_id,
                title=session.title,
            )
        finally:
            close_old_connections()
