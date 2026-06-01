from pydantic import BaseModel, Field


class SQLValidationRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10000)


class SQLValidationResponse(BaseModel):
    is_valid: bool
    normalized_sql: str | None = None
    reason: str | None = None
