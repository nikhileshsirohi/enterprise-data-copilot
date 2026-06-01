import pytest

from backend.ai_service.services.sql_executor import SQLExecutionError, SQLExecutor


@pytest.mark.django_db
def test_sql_executor_runs_safe_select() -> None:
    result = SQLExecutor().execute(
        "SELECT po_number FROM purchase_orders ORDER BY po_number",
        limit=2,
    )

    assert result.columns == ["po_number"]
    assert result.row_count == 2
    assert result.rows[0]["po_number"].startswith("PO")
    assert result.truncated is True


@pytest.mark.django_db
def test_sql_executor_rejects_unsafe_sql() -> None:
    with pytest.raises(SQLExecutionError):
        SQLExecutor().execute("DELETE FROM purchase_orders")
