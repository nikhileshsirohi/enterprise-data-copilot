from pydantic import BaseModel, Field


class MetadataSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class MetadataSearchResult(BaseModel):
    table: str
    column: str
    business_name: str
    description: str
    data_type: str
    examples: list[str]
    score: float


class MetadataSearchResponse(BaseModel):
    query: str
    results: list[MetadataSearchResult]
