from backend.ai_service.schemas.metadata import MetadataSearchResult
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
