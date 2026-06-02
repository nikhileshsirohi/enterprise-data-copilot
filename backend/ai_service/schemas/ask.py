from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    limit: int | None = Field(default=None, ge=1, le=500)
    user_id: int | None = Field(default=None, ge=1)
    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    persist: bool = True
    use_cache: bool = True


class AskResponse(BaseModel):
    question: str
    answer: str
    sql: str | None
    is_sql_valid: bool
    validation_reason: str | None
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool
    metadata: list[dict]
    execution_error: str | None = None
    retry_count: int = 0
    persisted: bool = False
    session_id: str | None = None
    user_message_id: int | None = None
    assistant_message_id: int | None = None
    cache_hit: bool = False
    cache_similarity: float | None = None
    cache_key: str | None = None
    used_chat_context: bool = False
    chat_context_message_count: int = 0
