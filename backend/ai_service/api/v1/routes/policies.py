from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.ai_service.schemas.policies import (
    PolicyDocumentListResponse,
    PolicyDocumentReindexRequest,
    PolicyDocumentReindexResponse,
    PolicySearchRequest,
    PolicySearchResponse,
)
from backend.ai_service.services.policy_documents import (
    PolicyDocumentError,
    PolicyDocumentIndexer,
    PolicyDocumentLoader,
    PolicyVectorSearcher,
    build_policy_indexer,
    build_policy_searcher,
)
from backend.shared.config import get_settings

router = APIRouter()


def get_policy_searcher() -> PolicyVectorSearcher:
    return build_policy_searcher()


def get_policy_indexer() -> PolicyDocumentIndexer:
    return build_policy_indexer()


def get_policy_loader() -> PolicyDocumentLoader:
    return PolicyDocumentLoader()


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


@router.post("/documents/reindex", response_model=PolicyDocumentReindexResponse)
def reindex_policy_documents(
    request: PolicyDocumentReindexRequest,
    indexer: Annotated[PolicyDocumentIndexer, Depends(get_policy_indexer)],
    loader: Annotated[PolicyDocumentLoader, Depends(get_policy_loader)],
) -> PolicyDocumentReindexResponse:
    settings = get_settings()
    try:
        documents = loader.load_directory(settings.policy_documents_dir)
        if request.reset:
            indexer.recreate_index()
        chunks_indexed = indexer.index_documents(documents)
    except PolicyDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return PolicyDocumentReindexResponse(
        index_name=settings.policy_documents_index,
        documents_found=len(documents),
        chunks_indexed=chunks_indexed,
        reset=request.reset,
    )
