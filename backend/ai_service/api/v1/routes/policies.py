from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.ai_service.schemas.policies import (
    PolicyDocumentDeleteResponse,
    PolicyDocumentListResponse,
    PolicyDocumentReindexRequest,
    PolicyDocumentReindexResponse,
    PolicyDocumentUploadRequest,
    PolicyDocumentUploadResponse,
    PolicySearchRequest,
    PolicySearchResponse,
)
from backend.ai_service.services.policy_documents import (
    PolicyDocumentError,
    PolicyDocumentIndexer,
    PolicyDocumentLoader,
    PolicyDocumentStorage,
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


def get_policy_storage() -> PolicyDocumentStorage:
    return PolicyDocumentStorage()


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


@router.post("/documents/upload", response_model=PolicyDocumentUploadResponse)
def upload_policy_document(
    request: PolicyDocumentUploadRequest,
    storage: Annotated[PolicyDocumentStorage, Depends(get_policy_storage)],
) -> PolicyDocumentUploadResponse:
    settings = get_settings()
    try:
        stored_document = storage.save_base64_document(
            directory=settings.policy_documents_dir,
            filename=request.filename,
            content_base64=request.content_base64,
            max_bytes=settings.policy_upload_max_bytes,
        )
    except PolicyDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PolicyDocumentUploadResponse(
        filename=stored_document.filename,
        source_path=stored_document.source_path,
        size_bytes=stored_document.size_bytes,
    )


@router.delete("/documents/{filename}", response_model=PolicyDocumentDeleteResponse)
def delete_policy_document(
    filename: str,
    storage: Annotated[PolicyDocumentStorage, Depends(get_policy_storage)],
) -> PolicyDocumentDeleteResponse:
    settings = get_settings()
    try:
        deleted_document = storage.delete_document(
            directory=settings.policy_documents_dir,
            filename=filename,
        )
    except PolicyDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PolicyDocumentDeleteResponse(
        filename=deleted_document.filename,
        source_path=deleted_document.source_path,
        deleted=deleted_document.deleted,
    )
