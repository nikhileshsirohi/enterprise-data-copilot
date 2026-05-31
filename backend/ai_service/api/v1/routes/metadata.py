from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.ai_service.schemas.metadata import MetadataSearchRequest, MetadataSearchResponse
from backend.ai_service.services.metadata_retriever import MetadataRetriever, get_metadata_retriever

router = APIRouter()


@router.post("/search", response_model=MetadataSearchResponse)
def search_metadata(
    request: MetadataSearchRequest,
    retriever: Annotated[MetadataRetriever, Depends(get_metadata_retriever)],
) -> MetadataSearchResponse:
    try:
        results = retriever.search(query=request.query, limit=request.limit)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return MetadataSearchResponse(query=request.query, results=results)
