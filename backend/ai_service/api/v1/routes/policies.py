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
from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_staff_user
from backend.ai_service.services.audit_logger import (
    PolicyDocumentAuditLogger,
    PolicyDocumentAuditRecord,
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


def get_policy_audit_logger() -> PolicyDocumentAuditLogger:
    return PolicyDocumentAuditLogger()


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
    current_user: Annotated[AuthenticatedUser, Depends(require_staff_user)],
    audit_logger: Annotated[PolicyDocumentAuditLogger, Depends(get_policy_audit_logger)],
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

    response = PolicyDocumentReindexResponse(
        index_name=settings.policy_documents_index,
        documents_found=len(documents),
        chunks_indexed=chunks_indexed,
        reset=request.reset,
    )
    audit_logger.record(
        PolicyDocumentAuditRecord(
            user_id=current_user.user_id,
            action="policy_document.reindex",
            entity_id=settings.policy_documents_index,
            status="SUCCESS",
            metadata=response.model_dump(),
        )
    )
    return response


@router.post("/documents/upload", response_model=PolicyDocumentUploadResponse)
def upload_policy_document(
    request: PolicyDocumentUploadRequest,
    storage: Annotated[PolicyDocumentStorage, Depends(get_policy_storage)],
    current_user: Annotated[AuthenticatedUser, Depends(require_staff_user)],
    audit_logger: Annotated[PolicyDocumentAuditLogger, Depends(get_policy_audit_logger)],
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

    response = PolicyDocumentUploadResponse(
        filename=stored_document.filename,
        source_path=stored_document.source_path,
        size_bytes=stored_document.size_bytes,
    )
    audit_logger.record(
        PolicyDocumentAuditRecord(
            user_id=current_user.user_id,
            action="policy_document.upload",
            entity_id=stored_document.filename,
            status="SUCCESS",
            metadata=response.model_dump(),
        )
    )
    return response


@router.delete("/documents/{filename}", response_model=PolicyDocumentDeleteResponse)
def delete_policy_document(
    filename: str,
    storage: Annotated[PolicyDocumentStorage, Depends(get_policy_storage)],
    indexer: Annotated[PolicyDocumentIndexer, Depends(get_policy_indexer)],
    current_user: Annotated[AuthenticatedUser, Depends(require_staff_user)],
    audit_logger: Annotated[PolicyDocumentAuditLogger, Depends(get_policy_audit_logger)],
) -> PolicyDocumentDeleteResponse:
    settings = get_settings()
    try:
        deleted_document = storage.delete_document(
            directory=settings.policy_documents_dir,
            filename=filename,
        )
        indexed_chunks_deleted = indexer.delete_document_chunks(deleted_document.document_id)
    except PolicyDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    response = PolicyDocumentDeleteResponse(
        filename=deleted_document.filename,
        source_path=deleted_document.source_path,
        deleted=deleted_document.deleted,
        document_id=deleted_document.document_id,
        indexed_chunks_deleted=indexed_chunks_deleted,
    )
    audit_logger.record(
        PolicyDocumentAuditRecord(
            user_id=current_user.user_id,
            action="policy_document.delete",
            entity_id=deleted_document.filename,
            status="SUCCESS",
            metadata=response.model_dump(),
        )
    )
    return response
