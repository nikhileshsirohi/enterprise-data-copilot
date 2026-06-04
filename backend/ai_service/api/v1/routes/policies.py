from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.ai_service.schemas.policies import (
    PolicyDocumentListResponse,
    PolicySearchRequest,
    PolicySearchResponse,
)
from backend.ai_service.services.policy_documents import PolicyVectorSearcher, build_policy_searcher
from backend.shared.config import get_settings

router = APIRouter()


def get_policy_searcher() -> PolicyVectorSearcher:
    return build_policy_searcher()


@router.post("/search", response_model=PolicySearchResponse)
def search_policies(
    request: PolicySearchRequest,
    searcher: Annotated[PolicyVectorSearcher, Depends(get_policy_searcher)],
) -> PolicySearchResponse:
    try:
        results = searcher.search(query=request.query, limit=request.limit)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return PolicySearchResponse(query=request.query, results=results)


@router.get("/documents", response_model=PolicyDocumentListResponse)
def list_policy_documents(
    searcher: Annotated[PolicyVectorSearcher, Depends(get_policy_searcher)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> PolicyDocumentListResponse:
    try:
        documents = searcher.list_documents(limit=limit)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    settings = get_settings()
    return PolicyDocumentListResponse(
        index_name=settings.policy_documents_index,
        documents=documents,
    )
