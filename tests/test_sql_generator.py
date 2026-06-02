from backend.ai_service.schemas.metadata import MetadataSearchResult
from backend.ai_service.services.chat_history import ChatContextMessage
from backend.ai_service.services.sql_generator import SQLGenerator


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
                score=10.0,
            ),
            MetadataSearchResult(
                table="purchase_orders",
                column="po_number",
                business_name="Purchase Order Number",
                description="Unique purchase order identifier.",
                data_type="string",
                examples=["PO1001"],
                score=8.0,
            ),
        ][:limit]


class FakeOllamaClient:
    def generate(self, model: str, prompt: str) -> str:
        assert model
        assert "committed quantity of PO1001" in prompt
        return """
        SELECT po.po_number, SUM(poi.commit_qty) AS committed_quantity
        FROM purchase_orders po
        JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
        WHERE po.po_number = 'PO1001'
        GROUP BY po.po_number;
        """


def test_sql_generator_returns_valid_sql() -> None:
    result = SQLGenerator(
        metadata_retriever=FakeMetadataRetriever(),
        llm_client=FakeOllamaClient(),
    ).generate("committed quantity of PO1001")

    assert result.is_valid is True
    assert result.sql is not None
    assert "purchase_order_items" in result.sql
    assert result.metadata[0]["column"] == "commit_qty"


def test_sql_generator_prompt_contains_join_rules() -> None:
    generator = SQLGenerator(
        metadata_retriever=FakeMetadataRetriever(),
        llm_client=FakeOllamaClient(),
    )
    prompt = generator._build_prompt(
        question="committed quantity of PO1001",
        metadata=FakeMetadataRetriever().search("committed quantity of PO1001"),
    )

    assert "purchase_order_items.purchase_order_id = purchase_orders.id" in prompt
    assert "Never use non-existent columns such as po_id" in prompt


def test_sql_generator_feedback_prompt_contains_database_error() -> None:
    class FeedbackFakeLLMClient:
        def generate(self, model: str, prompt: str) -> str:
            assert "Correction context" in prompt
            assert "column poi.po_id does not exist" in prompt
            return """
            SELECT po.po_number
            FROM purchase_orders po
            JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
            """

    result = SQLGenerator(
        metadata_retriever=FakeMetadataRetriever(),
        llm_client=FeedbackFakeLLMClient(),
    ).generate_with_feedback(
        question="committed quantity of PO1001",
        failed_sql=(
            "SELECT * FROM purchase_orders po "
            "JOIN purchase_order_items poi ON poi.po_id = po.id"
        ),
        execution_error="column poi.po_id does not exist",
    )

    assert result.is_valid is True
    assert result.sql is not None
    assert "purchase_order_id" in result.sql


def test_sql_generator_prompt_contains_customer_order_hints() -> None:
    generator = SQLGenerator(
        metadata_retriever=FakeMetadataRetriever(),
        llm_client=FakeOllamaClient(),
    )
    prompt = generator._build_prompt(
        question="Which material CUST00003 order and how much qty he committed",
        metadata=FakeMetadataRetriever().search("customer material order quantity"),
    )

    assert "filter c.code IN ('CUST00003')" in prompt
    assert "sales_order_items.order_qty AS quantity" in prompt
    assert "Do not use sales_orders.code" in prompt
    assert "Do not use purchase_order_items.commit_qty for customer orders" in prompt


def test_sql_generator_prompt_contains_recent_chat_context() -> None:
    generator = SQLGenerator(
        metadata_retriever=FakeMetadataRetriever(),
        llm_client=FakeOllamaClient(),
    )
    prompt = generator._build_prompt(
        question="what about its supplier?",
        metadata=FakeMetadataRetriever().search("supplier"),
        chat_context=[
            ChatContextMessage(role="USER", content="committed quantity of PO1001"),
            ChatContextMessage(
                role="ASSISTANT",
                content="PO1001 has a committed quantity of 4,983.",
            ),
        ],
    )

    assert "Recent conversation context:" in prompt
    assert "- USER: committed quantity of PO1001" in prompt
    assert "Use recent conversation context only to resolve follow-up references." in prompt
