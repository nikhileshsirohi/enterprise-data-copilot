from pydantic import BaseModel, Field


class SQLValidationRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10000)


class SQLValidationResponse(BaseModel):
    is_valid: bool
    normalized_sql: str | None = None
    reason: str | None = None


class SQLExecutionRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10000)
    limit: int | None = Field(default=None, ge=1, le=500)


class SQLExecutionResponse(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool
