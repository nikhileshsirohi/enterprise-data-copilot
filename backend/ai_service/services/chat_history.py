import logging
from dataclasses import dataclass
from uuid import uuid4

from backend.ai_service.schemas.ask import AskResponse
from backend.shared.django import ensure_django_setup

logger = logging.getLogger(__name__)


class ChatPersistenceError(ValueError):
    pass


@dataclass(frozen=True)
class ChatPersistenceResult:
    persisted: bool
    session_id: str | None = None
    user_message_id: int | None = None
    assistant_message_id: int | None = None


class ChatHistoryRecorder:
    def record_exchange(
        self,
        *,
        user_id: int | None,
        session_id: str | None,
        question: str,
        answer: AskResponse,
        limit: int | None,
    ) -> ChatPersistenceResult:
        ensure_django_setup()

        from django.contrib.auth import get_user_model

        from backend.django_app.core.models import ChatMessage, ChatSession

        if not user_id and not session_id:
            logger.info("chat_history.skip reason=no_user_or_session")
            return ChatPersistenceResult(persisted=False)

        session = None
        if session_id:
            session = ChatSession.objects.filter(session_id=session_id, is_active=True).first()
            if session and user_id and session.user_id != user_id:
                raise ChatPersistenceError("session_id does not belong to the supplied user_id.")

        if not session:
            if not user_id:
                raise ChatPersistenceError("user_id is required to create a new chat session.")

            user_model = get_user_model()
            user = user_model.objects.filter(id=user_id, is_active=True).first()
            if not user:
                raise ChatPersistenceError("Active user_id was not found.")

            session = ChatSession.objects.create(
                session_id=session_id or self._new_session_id(),
                user=user,
                title=self._build_title(question),
            )
            logger.info(
                "chat_history.session_created session_id=%s user_id=%s",
                session.session_id,
                user_id,
            )

        user_message = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.Role.USER,
            content=question,
            metadata={
                "limit": limit,
            },
        )
        assistant_message = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.Role.ASSISTANT,
            content=answer.answer,
            metadata=self._build_assistant_metadata(answer),
        )
        logger.info(
            (
                "chat_history.messages_created "
                "session_id=%s user_message_id=%s assistant_message_id=%s"
            ),
            session.session_id,
            user_message.id,
            assistant_message.id,
        )
        return ChatPersistenceResult(
            persisted=True,
            session_id=session.session_id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
        )

    def _new_session_id(self) -> str:
        return f"chat_{uuid4().hex}"

    def _build_title(self, question: str) -> str:
        return question[:80]

    def _build_assistant_metadata(self, answer: AskResponse) -> dict:
        return {
            "sql": answer.sql,
            "is_sql_valid": answer.is_sql_valid,
            "validation_reason": answer.validation_reason,
            "columns": answer.columns,
            "rows": answer.rows,
            "row_count": answer.row_count,
            "truncated": answer.truncated,
            "metadata_context": answer.metadata,
            "execution_error": answer.execution_error,
            "retry_count": answer.retry_count,
        }
