from django.contrib.auth import get_user_model

from backend.ai_service.schemas.ask import AskResponse
from backend.ai_service.services.audit_logger import (
    AskAuditLogger,
    AskAuditRecord,
    PolicyDocumentAuditLogger,
    PolicyDocumentAuditRecord,
)
from backend.django_app.core.models import AuditLog


def build_response() -> AskResponse:
    return AskResponse(
        question="committed quantity of PO1001",
        answer="PO1001 has a committed quantity of 4,983.",
        sql="SELECT 1",
        is_sql_valid=True,
        validation_reason=None,
        columns=["value"],
        rows=[{"value": 1}],
        row_count=1,
        truncated=False,
        metadata=[],
        persisted=True,
        session_id="chat_audit",
        cache_hit=False,
        used_chat_context=True,
        chat_context_message_count=2,
    )


def test_ask_audit_logger_records_success(db) -> None:
    user = get_user_model().objects.create_user(username="audit-user")

    AskAuditLogger().record(
        AskAuditRecord(
            user_id=user.id,
            session_id="chat_audit",
            question="committed quantity of PO1001",
            limit=5,
            status="SUCCESS",
            response=build_response(),
        )
    )

    audit = AuditLog.objects.get(action="ai.ask")
    assert audit.user == user
    assert audit.entity_type == "chat_session"
    assert audit.entity_id == "chat_audit"
    assert audit.metadata["status"] == "SUCCESS"
    assert audit.metadata["sql"] == "SELECT 1"
    assert audit.metadata["row_count"] == 1
    assert audit.metadata["used_chat_context"] is True
    assert audit.metadata["chat_context_message_count"] == 2


def test_ask_audit_logger_records_error_without_user(db) -> None:
    AskAuditLogger().record(
        AskAuditRecord(
            user_id=None,
            session_id=None,
            question="bad question",
            limit=None,
            status="SERVICE_ERROR",
            error="Ollama is not reachable",
            error_type="OllamaError",
        )
    )

    audit = AuditLog.objects.get(action="ai.ask")
    assert audit.user is None
    assert audit.entity_id == ""
    assert audit.metadata["status"] == "SERVICE_ERROR"
    assert audit.metadata["error"] == "Ollama is not reachable"
    assert audit.metadata["error_type"] == "OllamaError"
    assert audit.metadata["sql"] is None


def test_policy_document_audit_logger_records_admin_action(db) -> None:
    user = get_user_model().objects.create_user(username="policy-admin", is_staff=True)

    PolicyDocumentAuditLogger().record(
        PolicyDocumentAuditRecord(
            user_id=user.id,
            action="policy_document.upload",
            entity_id="benefits-policy.txt",
            status="SUCCESS",
            metadata={
                "filename": "benefits-policy.txt",
                "source_path": "data/company_policies/benefits-policy.txt",
                "size_bytes": 15,
            },
        )
    )

    audit = AuditLog.objects.get(action="policy_document.upload")
    assert audit.user == user
    assert audit.entity_type == "policy_document"
    assert audit.entity_id == "benefits-policy.txt"
    assert audit.metadata["status"] == "SUCCESS"
    assert audit.metadata["filename"] == "benefits-policy.txt"
    assert audit.metadata["size_bytes"] == 15
    assert audit.metadata["error"] is None
