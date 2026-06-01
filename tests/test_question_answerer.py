from backend.ai_service.schemas.sql import SQLExecutionResponse, SQLGenerationResponse
from backend.ai_service.services.question_answerer import QuestionAnswerer
from backend.ai_service.services.sql_executor import SQLExecutionError


class FakeSQLGenerator:
    def generate(self, question: str) -> SQLGenerationResponse:
        return SQLGenerationResponse(
            question=question,
            sql="SELECT po_number, committed_quantity FROM result",
            is_valid=True,
            validation_reason=None,
            metadata=[
                {
                    "table": "purchase_order_items",
                    "column": "commit_qty",
                    "business_name": "Committed Quantity",
                }
            ],
        )


class FakeSQLExecutor:
    def execute(self, sql: str, limit: int | None = None) -> SQLExecutionResponse:
        assert sql == "SELECT po_number, committed_quantity FROM result"
        assert limit == 5
        return SQLExecutionResponse(
            sql=sql,
            columns=["po_number", "committed_quantity"],
            rows=[{"po_number": "PO1001", "committed_quantity": "4983.000"}],
            row_count=1,
            truncated=False,
        )


class FakeLLMClient:
    def generate(self, model: str, prompt: str) -> str:
        assert model
        assert "PO1001" in prompt
        assert "4983.000" in prompt
        return "PO1001 has a committed quantity of 4,983."


class FakeUnsafeSQLGenerator:
    def generate(self, question: str) -> SQLGenerationResponse:
        return SQLGenerationResponse(
            question=question,
            sql="DELETE FROM purchase_orders",
            is_valid=False,
            validation_reason="Only SELECT statements are allowed.",
            metadata=[],
        )


class FakeWrongColumnSQLGenerator:
    def generate(self, question: str) -> SQLGenerationResponse:
        return SQLGenerationResponse(
            question=question,
            sql=(
                "SELECT * FROM purchase_orders po "
                "JOIN purchase_order_items poi ON poi.po_id = po.id"
            ),
            is_valid=True,
            validation_reason=None,
            metadata=[],
        )


class FakeFailingSQLExecutor:
    def execute(self, sql: str, limit: int | None = None) -> SQLExecutionResponse:
        raise SQLExecutionError(
            "Database rejected the generated SQL: column poi.po_id does not exist"
        )


def test_question_answerer_runs_generate_execute_summarize_flow() -> None:
    response = QuestionAnswerer(
        sql_generator=FakeSQLGenerator(),
        sql_executor=FakeSQLExecutor(),
        llm_client=FakeLLMClient(),
    ).ask("committed quantity of PO1001", limit=5)

    assert response.answer == "PO1001 has a committed quantity of 4,983."
    assert response.sql == "SELECT po_number, committed_quantity FROM result"
    assert response.row_count == 1
    assert response.rows[0]["committed_quantity"] == "4983.000"
    assert response.is_sql_valid is True


def test_question_answerer_stops_before_execution_when_sql_is_invalid() -> None:
    response = QuestionAnswerer(
        sql_generator=FakeUnsafeSQLGenerator(),
        sql_executor=FakeSQLExecutor(),
        llm_client=FakeLLMClient(),
    ).ask("delete purchase orders", limit=5)

    assert response.is_sql_valid is False
    assert response.row_count == 0
    assert "could not generate a safe read-only SQL query" in response.answer


def test_question_answerer_handles_database_rejected_generated_sql() -> None:
    response = QuestionAnswerer(
        sql_generator=FakeWrongColumnSQLGenerator(),
        sql_executor=FakeFailingSQLExecutor(),
        llm_client=FakeLLMClient(),
    ).ask("committed quantity of PO1001", limit=5)

    assert response.is_sql_valid is True
    assert response.row_count == 0
    assert response.execution_error is not None
    assert "database rejected" in response.answer.lower()
