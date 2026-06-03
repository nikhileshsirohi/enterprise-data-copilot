from fastapi import APIRouter, Depends, HTTPException, status

from backend.ai_service.schemas.ask import AskRequest, AskResponse
from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_authenticated_user
from backend.ai_service.services.audit_logger import AskAuditLogger, AskAuditRecord
from backend.ai_service.services.chat_history import (
    ChatHistoryReader,
    ChatHistoryRecorder,
    ChatPersistenceError,
)
from backend.ai_service.services.metadata_retriever import get_metadata_retriever
from backend.ai_service.services.question_answerer import QuestionAnswerer
from backend.ai_service.services.semantic_cache import SemanticCache
from backend.ai_service.services.sql_executor import SQLExecutionError
from backend.ai_service.services.sql_generator import SQLGenerator
from backend.shared.config import get_settings

router = APIRouter()
CurrentUserDependency = Depends(require_authenticated_user)


@router.post("/", response_model=AskResponse)
def ask_question(
    request: AskRequest,
    current_user: AuthenticatedUser = CurrentUserDependency,
) -> AskResponse:
    audit_logger = AskAuditLogger()
    effective_user_id = request.user_id or current_user.user_id
    if effective_user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request user_id does not match the authenticated user.",
        )

    try:
        settings = get_settings()
        chat_context = ChatHistoryReader().get_recent_context(
            session_id=request.session_id,
            user_id=effective_user_id,
            limit=settings.chat_history_context_limit,
        )
        allow_semantic_cache = request.use_cache and not chat_context
        semantic_cache = SemanticCache()
        cached = semantic_cache.get(request.question) if allow_semantic_cache else None
        if cached:
            response = cached.response
        else:
            sql_generator = SQLGenerator(metadata_retriever=get_metadata_retriever())
            response = QuestionAnswerer(sql_generator=sql_generator).ask(
                question=request.question,
                limit=request.limit,
                chat_context=chat_context,
            )
            cache_key = (
                semantic_cache.set(request.question, response) if allow_semantic_cache else None
            )
            if cache_key:
                response = response.model_copy(update={"cache_key": cache_key})

        response = response.model_copy(
            update={
                "used_chat_context": bool(chat_context),
                "chat_context_message_count": len(chat_context),
            }
        )
        if request.persist:
            persistence = ChatHistoryRecorder().record_exchange(
                user_id=effective_user_id,
                session_id=request.session_id,
                question=request.question,
                answer=response,
                limit=request.limit,
            )
            response = response.model_copy(
                update={
                    "persisted": persistence.persisted,
                    "session_id": persistence.session_id,
                    "user_message_id": persistence.user_message_id,
                    "assistant_message_id": persistence.assistant_message_id,
                }
            )
        audit_logger.record(
            AskAuditRecord(
                user_id=effective_user_id,
                session_id=response.session_id or request.session_id,
                question=request.question,
                limit=request.limit,
                status="SUCCESS",
                response=response,
            )
        )
        return response
    except ChatPersistenceError as exc:
        audit_logger.record(
            AskAuditRecord(
                user_id=effective_user_id,
                session_id=request.session_id,
                question=request.question,
                limit=request.limit,
                status="CLIENT_ERROR",
                error=str(exc),
                error_type=exc.__class__.__name__,
            )
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLExecutionError as exc:
        audit_logger.record(
            AskAuditRecord(
                user_id=effective_user_id,
                session_id=request.session_id,
                question=request.question,
                limit=request.limit,
                status="CLIENT_ERROR",
                error=str(exc),
                error_type=exc.__class__.__name__,
            )
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ConnectionError, RuntimeError, ValueError) as exc:
        audit_logger.record(
            AskAuditRecord(
                user_id=effective_user_id,
                session_id=request.session_id,
                question=request.question,
                limit=request.limit,
                status="SERVICE_ERROR",
                error=str(exc),
                error_type=exc.__class__.__name__,
            )
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
