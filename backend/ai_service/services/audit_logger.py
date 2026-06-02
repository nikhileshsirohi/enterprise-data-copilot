import logging
from dataclasses import dataclass

from backend.ai_service.schemas.ask import AskResponse
from backend.shared.django import ensure_django_setup

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AskAuditRecord:
    user_id: int | None
    session_id: str | None
    question: str
    limit: int | None
    status: str
    response: AskResponse | None = None
    error: str | None = None
    error_type: str | None = None


class AskAuditLogger:
    action = "ai.ask"

    def record(self, record: AskAuditRecord) -> None:
        try:
            ensure_django_setup()

            from django.contrib.auth import get_user_model

            from backend.django_app.core.models import AuditLog

            user = None
            if record.user_id:
                user = get_user_model().objects.filter(id=record.user_id).first()

            AuditLog.objects.create(
                user=user,
                action=self.action,
                entity_type="chat_session",
                entity_id=record.session_id or "",
                metadata=self._build_metadata(record),
            )
            logger.info(
                "audit.ai_ask_recorded status=%s user_id=%s session_id=%s",
                record.status,
                record.user_id,
                record.session_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("audit.ai_ask_failed error=%s", exc)

    def _build_metadata(self, record: AskAuditRecord) -> dict:
        response = record.response
        return {
            "question": record.question,
            "limit": record.limit,
            "status": record.status,
            "sql": response.sql if response else None,
            "is_sql_valid": response.is_sql_valid if response else None,
            "row_count": response.row_count if response else None,
            "truncated": response.truncated if response else None,
            "cache_hit": response.cache_hit if response else None,
            "cache_similarity": response.cache_similarity if response else None,
            "cache_key": response.cache_key if response else None,
            "used_chat_context": response.used_chat_context if response else None,
            "chat_context_message_count": (
                response.chat_context_message_count if response else None
            ),
            "persisted": response.persisted if response else None,
            "retry_count": response.retry_count if response else None,
            "execution_error": response.execution_error if response else None,
            "error": record.error,
            "error_type": record.error_type,
        }
