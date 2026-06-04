from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.ai_service.schemas.policies import PolicySearchRequest, PolicySearchResponse
from backend.ai_service.services.policy_documents import PolicyVectorSearcher, build_policy_searcher

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
