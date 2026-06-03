from datetime import UTC, datetime, timedelta

import jwt
import pytest
from django.contrib.auth import get_user_model
from fastapi.testclient import TestClient

from backend.ai_service.main import app
from backend.shared.config import get_settings


def build_access_token(user_id: int, *, token_type: str = "access") -> str:
    settings = get_settings()
    payload = {
        "token_type": token_type,
        "user_id": user_id,
        "exp": datetime.now(tz=UTC) + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def test_health_endpoint_stays_public() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health/")

    assert response.status_code == 200, response.json()


@pytest.mark.django_db(transaction=True)
def test_protected_endpoint_accepts_valid_django_access_token() -> None:
    user = get_user_model().objects.create_user(username="fastapi-user")
    token = build_access_token(user.id)
    client = TestClient(app)

    response = client.post(
        "/api/v1/sql/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"sql": "SELECT 1"},
    )

    assert response.status_code == 200, response.json()
    assert response.json()["is_valid"] is True


@pytest.mark.django_db(transaction=True)
def test_protected_endpoint_rejects_refresh_token_type() -> None:
    user = get_user_model().objects.create_user(username="refresh-user")
    token = build_access_token(user.id, token_type="refresh")
    client = TestClient(app)

    response = client.post(
        "/api/v1/sql/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"sql": "SELECT 1"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Access token is required."
