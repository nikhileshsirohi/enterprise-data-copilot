from fastapi.testclient import TestClient

from backend.ai_service.api.v1.routes.metadata import get_metadata_retriever
from backend.ai_service.main import app
from backend.ai_service.schemas.metadata import MetadataSearchResult
from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_authenticated_user


class FakeMetadataRetriever:
    def search(self, query: str, limit: int = 5) -> list[MetadataSearchResult]:
        return [
            MetadataSearchResult(
                table="purchase_order_items",
                column="commit_qty",
                business_name="Committed Quantity",
                description="Quantity committed by supplier for a purchase order line.",
                data_type="decimal",
                examples=["committed quantity of PO1001"],
                score=4.2,
            )
        ][:limit]


def test_ai_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-service"}


def test_metadata_search_endpoint_returns_results() -> None:
    app.dependency_overrides[get_metadata_retriever] = lambda: FakeMetadataRetriever()
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=1,
        username="api-user",
        is_staff=True,
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/metadata/search",
        json={"query": "committed quantity of PO1001", "limit": 3},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "committed quantity of PO1001"
    assert body["results"][0]["table"] == "purchase_order_items"
    assert body["results"][0]["column"] == "commit_qty"


def test_metadata_search_requires_access_token() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.post(
        "/api/v1/metadata/search",
        json={"query": "committed quantity of PO1001", "limit": 3},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer access token is required."
