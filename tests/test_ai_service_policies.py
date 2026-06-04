from fastapi.testclient import TestClient

from backend.ai_service.api.v1.routes.policies import get_policy_searcher
from backend.ai_service.main import app
from backend.ai_service.schemas.policies import PolicyDocumentSummary, PolicySearchResult
from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_authenticated_user


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
