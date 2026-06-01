from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    limit: int | None = Field(default=None, ge=1, le=500)


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
