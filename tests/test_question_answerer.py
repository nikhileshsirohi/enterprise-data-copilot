from backend.ai_service.schemas.sql import SQLExecutionResponse, SQLGenerationResponse
from backend.ai_service.services.chat_history import ChatContextMessage
from backend.ai_service.services.question_answerer import QuestionAnswerer
from backend.ai_service.services.sql_executor import SQLExecutionError


class FakeSQLGenerator:
    def generate(
        self,
        question: str,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> SQLGenerationResponse:
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


class FakeWorkflowStateStore:
    def __init__(self) -> None:
        self.checkpoints = []
        self.completions = []

    def start_run(self, *, question: str, limit: int | None, chat_context_count: int) -> str:
        return "workflow_test"

    def append_checkpoint(self, run_id, checkpoint) -> None:
        self.checkpoints.append((run_id, checkpoint))

    def complete_run(self, run_id: str, *, status: str, metadata: dict | None = None) -> None:
        self.completions.append((run_id, status, metadata))


class FakeUnsafeSQLGenerator:
    def generate(
        self,
        question: str,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> SQLGenerationResponse:
        return SQLGenerationResponse(
            question=question,
            sql="DELETE FROM purchase_orders",
            is_valid=False,
            validation_reason="Only SELECT statements are allowed.",
            metadata=[],
        )


class FakeWrongColumnSQLGenerator:
    def generate(
        self,
        question: str,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> SQLGenerationResponse:
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

    def generate_with_feedback(
        self,
        question: str,
        failed_sql: str,
        execution_error: str,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> SQLGenerationResponse:
        assert "po_id" in failed_sql
        assert "does not exist" in execution_error
        return SQLGenerationResponse(
            question=question,
            sql=(
                "SELECT po.po_number, SUM(poi.commit_qty) AS committed_quantity "
                "FROM purchase_orders po "
                "JOIN purchase_order_items poi ON poi.purchase_order_id = po.id "
                "WHERE po.po_number = 'PO1001' "
                "GROUP BY po.po_number"
            ),
            is_valid=True,
            validation_reason=None,
            metadata=[],
        )


class FakeAlwaysWrongColumnSQLGenerator:
    def generate(
        self,
        question: str,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> SQLGenerationResponse:
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

    def generate_with_feedback(
        self,
        question: str,
        failed_sql: str,
        execution_error: str,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> SQLGenerationResponse:
        return self.generate(question)


class FakeFailingSQLExecutor:
    def execute(self, sql: str, limit: int | None = None) -> SQLExecutionResponse:
        raise SQLExecutionError(
            "Database rejected the generated SQL: column poi.po_id does not exist"
        )


class FakeFailOnceSQLExecutor:
    def __init__(self) -> None:
        self.call_count = 0

    def execute(self, sql: str, limit: int | None = None) -> SQLExecutionResponse:
        self.call_count += 1
        if self.call_count == 1:
            raise SQLExecutionError(
                "Database rejected the generated SQL: column poi.po_id does not exist"
            )
        assert "purchase_order_id" in sql
        return SQLExecutionResponse(
            sql=sql,
            columns=["po_number", "committed_quantity"],
            rows=[{"po_number": "PO1001", "committed_quantity": "4983.000"}],
            row_count=1,
            truncated=False,
        )


def test_question_answerer_runs_generate_execute_summarize_flow() -> None:
    state_store = FakeWorkflowStateStore()
    response = QuestionAnswerer(
        sql_generator=FakeSQLGenerator(),
        sql_executor=FakeSQLExecutor(),
        llm_client=FakeLLMClient(),
        state_store=state_store,
    ).ask("committed quantity of PO1001", limit=5)

    assert response.answer == "PO1001 has a committed quantity of 4,983."
    assert response.sql == "SELECT po_number, committed_quantity FROM result"
    assert response.row_count == 1
    assert response.rows[0]["committed_quantity"] == "4983.000"
    assert response.is_sql_valid is True
    assert response.workflow_run_id == "workflow_test"
    assert state_store.completions[-1][1] == "SUCCESS"


def test_question_answerer_stops_before_execution_when_sql_is_invalid() -> None:
    response = QuestionAnswerer(
        sql_generator=FakeUnsafeSQLGenerator(),
        sql_executor=FakeSQLExecutor(),
        llm_client=FakeLLMClient(),
        state_store=FakeWorkflowStateStore(),
    ).ask("delete purchase orders", limit=5)

    assert response.is_sql_valid is False
    assert response.row_count == 0
    assert "could not generate a safe read-only SQL query" in response.answer


def test_question_answerer_retries_after_database_rejected_generated_sql() -> None:
    sql_executor = FakeFailOnceSQLExecutor()

    response = QuestionAnswerer(
        sql_generator=FakeWrongColumnSQLGenerator(),
        sql_executor=sql_executor,
        llm_client=FakeLLMClient(),
        state_store=FakeWorkflowStateStore(),
    ).ask("committed quantity of PO1001", limit=5)

    assert response.is_sql_valid is True
    assert response.row_count == 1
    assert response.retry_count == 1
    assert response.execution_error is None
    assert sql_executor.call_count == 2


def test_question_answerer_returns_error_after_retry_limit() -> None:
    response = QuestionAnswerer(
        sql_generator=FakeAlwaysWrongColumnSQLGenerator(),
        sql_executor=FakeFailingSQLExecutor(),
        llm_client=FakeLLMClient(),
        state_store=FakeWorkflowStateStore(),
    ).ask("committed quantity of PO1001", limit=5)

    assert response.is_sql_valid is True
    assert response.row_count == 0
    assert response.retry_count == 1
    assert response.execution_error is not None
    assert "database rejected" in response.answer.lower()


def test_question_answerer_passes_chat_context_to_generator_and_answer_prompt() -> None:
    class ContextAwareSQLGenerator:
        def generate(
            self,
            question: str,
            chat_context: list[ChatContextMessage] | None = None,
        ) -> SQLGenerationResponse:
            assert question == "what about its supplier?"
            assert chat_context
            assert chat_context[0].content == "committed quantity of PO1001"
            return SQLGenerationResponse(
                question=question,
                sql="SELECT supplier_name FROM result",
                is_valid=True,
                validation_reason=None,
                metadata=[],
            )

    class ContextAwareExecutor:
        def execute(self, sql: str, limit: int | None = None) -> SQLExecutionResponse:
            return SQLExecutionResponse(
                sql=sql,
                columns=["supplier_name"],
                rows=[{"supplier_name": "Supplier 1"}],
                row_count=1,
                truncated=False,
            )

    class ContextAwareLLMClient:
        def generate(self, model: str, prompt: str) -> str:
            assert "committed quantity of PO1001" in prompt
            assert "what about its supplier?" in prompt
            return "The supplier is Supplier 1."

    response = QuestionAnswerer(
        sql_generator=ContextAwareSQLGenerator(),
        sql_executor=ContextAwareExecutor(),
        llm_client=ContextAwareLLMClient(),
        state_store=FakeWorkflowStateStore(),
    ).ask(
        "what about its supplier?",
        chat_context=[ChatContextMessage(role="USER", content="committed quantity of PO1001")],
    )

    assert response.used_chat_context is True
    assert response.chat_context_message_count == 1
    assert response.answer == "The supplier is Supplier 1."
