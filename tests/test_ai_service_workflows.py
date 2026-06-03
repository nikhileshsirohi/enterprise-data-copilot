from fastapi.testclient import TestClient

from backend.ai_service.api.v1.routes.workflows import get_workflow_state_store
from backend.ai_service.main import app
from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_authenticated_user


class FakeWorkflowStateStore:
    def __init__(self, payload: dict | None) -> None:
        self.payload = payload

    def get_run(self, run_id: str) -> dict | None:
        if self.payload:
            assert run_id == self.payload["run_id"]
        return self.payload


def test_workflow_run_endpoint_returns_redis_trace() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=1,
        username="api-user",
        is_staff=False,
    )
    app.dependency_overrides[get_workflow_state_store] = lambda: FakeWorkflowStateStore(
        {
            "run_id": "workflow_123",
            "status": "SUCCESS",
            "question": "committed quantity of PO1001",
            "checkpoints": [
                {
                    "node": "generate_sql",
                    "status": "VALID",
                    "metadata": {"sql": "SELECT 1"},
                }
            ],
            "result": {"row_count": 1},
        }
    )
    client = TestClient(app)

    response = client.get("/api/v1/workflows/workflow_123")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "workflow_123"
    assert body["status"] == "SUCCESS"
    assert body["checkpoints"][0]["node"] == "generate_sql"
    assert body["result"]["row_count"] == 1


def test_workflow_run_endpoint_returns_404_when_missing() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=1,
        username="api-user",
        is_staff=False,
    )
    app.dependency_overrides[get_workflow_state_store] = lambda: FakeWorkflowStateStore(None)
    client = TestClient(app)

    response = client.get("/api/v1/workflows/missing")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow run was not found or expired."
