from fastapi.testclient import TestClient

from backend.ai_service.main import app
from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_authenticated_user
from backend.ai_service.services.sql_validator import SQLValidator


def test_sql_validator_allows_select() -> None:
    result = SQLValidator().validate(
        "SELECT po_number FROM purchase_orders WHERE po_number = 'PO1001';"
    )

    assert result.is_valid is True
    assert (
        result.normalized_sql
        == "SELECT po_number FROM purchase_orders WHERE po_number = 'PO1001'"
    )


def test_sql_validator_blocks_delete() -> None:
    result = SQLValidator().validate("DELETE FROM purchase_orders WHERE po_number = 'PO1001'")

    assert result.is_valid is False
    assert "Only SELECT" in result.reason


def test_sql_validator_blocks_multiple_statements() -> None:
    result = SQLValidator().validate("SELECT 1; SELECT 2;")

    assert result.is_valid is False
    assert result.reason == "Only one SQL statement is allowed."


def test_sql_validator_blocks_comments() -> None:
    result = SQLValidator().validate("SELECT * FROM purchase_orders -- bypass")

    assert result.is_valid is False
    assert "comments" in result.reason


def test_sql_validation_endpoint() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=1,
        username="api-user",
        is_staff=False,
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/sql/validate",
        json={"sql": "SELECT stock_qty FROM inventory"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "is_valid": True,
        "normalized_sql": "SELECT stock_qty FROM inventory",
        "reason": None,
    }
