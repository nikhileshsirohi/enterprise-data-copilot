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


class PolicyDocumentSummary(BaseModel):
    document_id: str
    document_title: str
    source_path: str
    chunk_count: int
    max_chunk_index: int | None = None


class PolicyDocumentListResponse(BaseModel):
    index_name: str
    documents: list[PolicyDocumentSummary]


class PolicyDocumentReindexRequest(BaseModel):
    reset: bool = False


class PolicyDocumentReindexResponse(BaseModel):
    index_name: str
    documents_found: int
    chunks_indexed: int
    reset: bool


class PolicyDocumentUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)


class PolicyDocumentUploadResponse(BaseModel):
    filename: str
    source_path: str
    size_bytes: int


class PolicyDocumentDeleteResponse(BaseModel):
    filename: str
    source_path: str
    deleted: bool
