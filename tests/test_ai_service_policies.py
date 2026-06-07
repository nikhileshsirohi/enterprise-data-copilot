from fastapi.testclient import TestClient

from backend.ai_service.api.v1.routes.policies import (
    get_policy_audit_logger,
    get_policy_indexer,
    get_policy_loader,
    get_policy_searcher,
    get_policy_storage,
)
from backend.ai_service.main import app
from backend.ai_service.schemas.policies import PolicyDocumentSummary, PolicySearchResult
from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_authenticated_user
from backend.ai_service.services.policy_documents import (
    DeletedPolicyDocument,
    PolicyDocument,
    StoredPolicyDocument,
)


class FakePolicySearcher:
    def search(self, query: str, limit: int = 5):
        assert query == "remote work vpn"
        return [
            PolicySearchResult(
                document_id="remote-work-policy",
                document_title="Remote Work Policy",
                source_path="data/company_policies/remote-work-policy.pdf",
                chunk_id="remote-work-policy:0",
                chunk_index=0,
                text="Company data must be accessed using VPN.",
                score=0.9,
            )
        ][:limit]

    def list_documents(self, limit: int = 100):
        return [
            PolicyDocumentSummary(
                document_id="remote-work-policy",
                document_title="Remote Work Policy",
                source_path="data/company_policies/remote-work-policy.pdf",
                chunk_count=2,
                max_chunk_index=1,
            )
        ][:limit]


class FakePolicyLoader:
    def load_directory(self, directory: str):
        assert directory == "data/company_policies"
        return [
            PolicyDocument(
                document_id="remote-work-policy",
                title="Remote Work Policy",
                source_path="data/company_policies/remote-work-policy.pdf",
                text="Company data must be accessed using VPN.",
            )
        ]


class FakePolicyIndexer:
    def __init__(self) -> None:
        self.recreated = False

    def recreate_index(self) -> None:
        self.recreated = True

    def index_documents(self, documents):
        assert len(documents) == 1
        assert self.recreated is True
        return 2

    def delete_document_chunks(self, document_id: str):
        assert document_id == "benefits-policy"
        return 4


class FakePolicyStorage:
    def save_base64_document(self, *, directory, filename, content_base64, max_bytes):
        assert directory == "data/company_policies"
        assert filename == "benefits-policy.txt"
        assert content_base64 == "QmVuZWZpdHMgcG9saWN5"
        assert max_bytes == 10_485_760
        return StoredPolicyDocument(
            filename="benefits-policy.txt",
            source_path="data/company_policies/benefits-policy.txt",
            size_bytes=15,
        )

    def delete_document(self, *, directory, filename):
        assert directory == "data/company_policies"
        assert filename == "benefits-policy.txt"
        return DeletedPolicyDocument(
            filename="benefits-policy.txt",
            source_path="data/company_policies/benefits-policy.txt",
            deleted=True,
            document_id="benefits-policy",
        )


class FakePolicyAuditLogger:
    def record(self, record) -> None:
        assert record.user_id == 1
        assert record.action.startswith("policy_document.")
        assert record.status == "SUCCESS"


def test_policy_search_endpoint_returns_vector_results() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=1,
        username="staff-user",
        is_staff=True,
    )
    app.dependency_overrides[get_policy_searcher] = lambda: FakePolicySearcher()
    client = TestClient(app)

    response = client.post(
        "/api/v1/policies/search",
        json={"query": "remote work vpn", "limit": 3},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "remote work vpn"
    assert body["results"][0]["document_id"] == "remote-work-policy"
    assert body["results"][0]["score"] == 0.9


def test_policy_search_endpoint_requires_staff() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=2,
        username="normal-user",
        is_staff=False,
    )
    app.dependency_overrides[get_policy_searcher] = lambda: FakePolicySearcher()
    client = TestClient(app)

    response = client.post(
        "/api/v1/policies/search",
        json={"query": "remote work vpn", "limit": 3},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "Staff access is required."


def test_policy_documents_endpoint_returns_indexed_documents() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=1,
        username="staff-user",
        is_staff=True,
    )
    app.dependency_overrides[get_policy_searcher] = lambda: FakePolicySearcher()
    client = TestClient(app)

    response = client.get("/api/v1/policies/documents")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["index_name"] == "company_policy_documents"
    assert body["documents"] == [
        {
            "document_id": "remote-work-policy",
            "document_title": "Remote Work Policy",
            "source_path": "data/company_policies/remote-work-policy.pdf",
            "chunk_count": 2,
            "max_chunk_index": 1,
        }
    ]


def test_policy_documents_reindex_endpoint_indexes_configured_directory() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=1,
        username="staff-user",
        is_staff=True,
    )
    app.dependency_overrides[get_policy_loader] = lambda: FakePolicyLoader()
    app.dependency_overrides[get_policy_indexer] = lambda: FakePolicyIndexer()
    app.dependency_overrides[get_policy_audit_logger] = lambda: FakePolicyAuditLogger()
    client = TestClient(app)

    response = client.post("/api/v1/policies/documents/reindex", json={"reset": True})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "index_name": "company_policy_documents",
        "documents_found": 1,
        "chunks_indexed": 2,
        "reset": True,
    }


def test_policy_documents_upload_endpoint_saves_policy_file() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=1,
        username="staff-user",
        is_staff=True,
    )
    app.dependency_overrides[get_policy_storage] = lambda: FakePolicyStorage()
    app.dependency_overrides[get_policy_audit_logger] = lambda: FakePolicyAuditLogger()
    client = TestClient(app)

    response = client.post(
        "/api/v1/policies/documents/upload",
        json={
            "filename": "benefits-policy.txt",
            "content_base64": "QmVuZWZpdHMgcG9saWN5",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "filename": "benefits-policy.txt",
        "source_path": "data/company_policies/benefits-policy.txt",
        "size_bytes": 15,
    }


def test_policy_documents_delete_endpoint_removes_policy_file() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=1,
        username="staff-user",
        is_staff=True,
    )
    app.dependency_overrides[get_policy_storage] = lambda: FakePolicyStorage()
    app.dependency_overrides[get_policy_indexer] = lambda: FakePolicyIndexer()
    app.dependency_overrides[get_policy_audit_logger] = lambda: FakePolicyAuditLogger()
    client = TestClient(app)

    response = client.delete("/api/v1/policies/documents/benefits-policy.txt")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "filename": "benefits-policy.txt",
        "source_path": "data/company_policies/benefits-policy.txt",
        "deleted": True,
        "document_id": "benefits-policy",
        "indexed_chunks_deleted": 4,
    }
