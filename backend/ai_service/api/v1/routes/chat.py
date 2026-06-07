from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.ai_service.schemas.chat import (
    ChatSessionArchiveResponse,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionRenameRequest,
    ChatSessionRenameResponse,
)
from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_authenticated_user
from backend.ai_service.services.chat_sessions import ChatSessionNotFoundError, ChatSessionReader

router = APIRouter()


def get_chat_session_reader() -> ChatSessionReader:
    return ChatSessionReader()


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_chat_sessions(
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    reader: Annotated[ChatSessionReader, Depends(get_chat_session_reader)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ChatSessionListResponse:
    sessions = reader.list_sessions(
        user_id=current_user.user_id,
        can_view_all=current_user.is_superuser,
        limit=limit,
    )
    return ChatSessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_chat_session(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    reader: Annotated[ChatSessionReader, Depends(get_chat_session_reader)],
    message_limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ChatSessionDetailResponse:
    try:
        return reader.get_session(
            user_id=current_user.user_id,
            session_id=session_id,
            can_view_all=current_user.is_superuser,
            message_limit=message_limit,
        )
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}", response_model=ChatSessionArchiveResponse)
def archive_chat_session(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    reader: Annotated[ChatSessionReader, Depends(get_chat_session_reader)],
) -> ChatSessionArchiveResponse:
    try:
        return reader.archive_session(user_id=current_user.user_id, session_id=session_id)
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/sessions/{session_id}/title", response_model=ChatSessionRenameResponse)
def rename_chat_session(
    session_id: str,
    request: ChatSessionRenameRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    reader: Annotated[ChatSessionReader, Depends(get_chat_session_reader)],
) -> ChatSessionRenameResponse:
    try:
        return reader.rename_session(
            user_id=current_user.user_id,
            session_id=session_id,
            title=request.title,
        )
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
