import json
import logging
from dataclasses import dataclass
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from backend.ai_service.schemas.ask import AskResponse
from backend.shared.config import get_settings
from backend.shared.django import ensure_django_setup
from backend.shared.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class ChatPersistenceError(ValueError):
    pass


@dataclass(frozen=True)
class ChatPersistenceResult:
    persisted: bool
    session_id: str | None = None
    user_message_id: int | None = None
    assistant_message_id: int | None = None


@dataclass(frozen=True)
class ChatContextMessage:
    role: str
    content: str


class RedisChatMemory:
    def __init__(self, redis_client: Redis | None = None) -> None:
        self.redis_client = redis_client or get_redis_client()

    def append_messages(
        self,
        *,
        session_id: str,
        messages: list[ChatContextMessage],
    ) -> None:
        if not messages:
            return

        settings = get_settings()
        key = self._key(session_id)
        payloads = [
            json.dumps({"role": message.role, "content": message.content})
            for message in messages
        ]
        try:
            self.redis_client.rpush(key, *payloads)
            self.redis_client.ltrim(key, -settings.chat_history_context_limit, -1)
            self.redis_client.expire(key, settings.chat_history_redis_ttl_seconds)
            logger.info(
                "chat_history.redis_appended session_id=%s message_count=%s",
                session_id,
                len(messages),
            )
        except RedisError as exc:
            logger.warning(
                "chat_history.redis_append_failed session_id=%s error=%s",
                session_id,
                exc,
            )

    def get_recent_messages(self, *, session_id: str, limit: int) -> list[ChatContextMessage]:
        if limit <= 0:
            return []

        try:
            raw_messages = self.redis_client.lrange(self._key(session_id), -limit, -1)
        except RedisError as exc:
            logger.warning("chat_history.redis_read_failed session_id=%s error=%s", session_id, exc)
            return []

        messages = []
        for raw_message in raw_messages:
            try:
                payload = json.loads(raw_message)
                messages.append(
                    ChatContextMessage(
                        role=str(payload["role"]),
                        content=str(payload["content"]),
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "chat_history.redis_message_invalid session_id=%s error=%s",
                    session_id,
                    exc,
                )
        if messages:
            logger.info(
                "chat_history.redis_context_loaded session_id=%s message_count=%s",
                session_id,
                len(messages),
            )
        return messages

    def replace_messages(
        self,
        *,
        session_id: str,
        messages: list[ChatContextMessage],
    ) -> None:
        if not messages:
            return

        settings = get_settings()
        key = self._key(session_id)
        payloads = [
            json.dumps({"role": message.role, "content": message.content})
            for message in messages[-settings.chat_history_context_limit :]
        ]
        try:
            self.redis_client.delete(key)
            self.redis_client.rpush(key, *payloads)
            self.redis_client.expire(key, settings.chat_history_redis_ttl_seconds)
            logger.info(
                "chat_history.redis_warmed session_id=%s message_count=%s",
                session_id,
                len(payloads),
            )
        except RedisError as exc:
            logger.warning("chat_history.redis_warm_failed session_id=%s error=%s", session_id, exc)

    def _key(self, session_id: str) -> str:
        settings = get_settings()
        return f"{settings.redis_chat_history_prefix}:{session_id}"


class ChatHistoryReader:
    def __init__(self, redis_memory: RedisChatMemory | None = None) -> None:
        self.redis_memory = redis_memory or RedisChatMemory()

    def get_recent_context(
        self,
        *,
        session_id: str | None,
        user_id: int | None,
        limit: int,
    ) -> list[ChatContextMessage]:
        ensure_django_setup()

        from backend.django_app.core.models import ChatMessage, ChatSession

        if not session_id or limit <= 0:
            logger.info("chat_history.context_skip reason=no_session_or_limit")
            return []

        session = ChatSession.objects.filter(session_id=session_id, is_active=True).first()
        if not session:
            logger.info("chat_history.context_not_found session_id=%s", session_id)
            return []

        if user_id and session.user_id != user_id:
            raise ChatPersistenceError("session_id does not belong to the supplied user_id.")

        redis_context = self.redis_memory.get_recent_messages(session_id=session_id, limit=limit)
        if redis_context:
            return redis_context

        messages = list(
            session.messages.filter(
                role__in=[ChatMessage.Role.USER, ChatMessage.Role.ASSISTANT],
            )
            .order_by("-created_at", "-id")[:limit]
            .values_list("role", "content")
        )
        context = [
            ChatContextMessage(role=role, content=content)
            for role, content in reversed(messages)
        ]
        logger.info(
            "chat_history.context_loaded session_id=%s message_count=%s",
            session_id,
            len(context),
        )
        self.redis_memory.replace_messages(session_id=session_id, messages=context)
        return context


class ChatHistoryRecorder:
    def __init__(self, redis_memory: RedisChatMemory | None = None) -> None:
        self.redis_memory = redis_memory or RedisChatMemory()

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
        self.redis_memory.append_messages(
            session_id=session.session_id,
            messages=[
                ChatContextMessage(role=user_message.role, content=user_message.content),
                ChatContextMessage(role=assistant_message.role, content=assistant_message.content),
            ],
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
