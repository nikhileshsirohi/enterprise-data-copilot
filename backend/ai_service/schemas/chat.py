from datetime import datetime

from pydantic import BaseModel, Field


class ChatSessionSummary(BaseModel):
    session_id: str
    user_id: int
    username: str
    title: str
    is_active: bool
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionSummary]


class ChatMessageDetail(BaseModel):
    id: int
    role: str
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class ChatSessionDetailResponse(BaseModel):
    session_id: str
    user_id: int
    username: str
    title: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageDetail]


class ChatSessionArchiveResponse(BaseModel):
    session_id: str
    archived: bool
    is_active: bool


class ChatSessionRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ChatSessionRenameResponse(BaseModel):
    session_id: str
    title: str
