from pydantic import BaseModel, Field


class PolicySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20)


class PolicySearchResult(BaseModel):
    document_id: str
    document_title: str
    source_path: str
    chunk_id: str
    chunk_index: int
    text: str
    score: float


class PolicySearchResponse(BaseModel):
    query: str
    results: list[PolicySearchResult]
