import logging
import re

from backend.ai_service.schemas.metadata import MetadataSearchResult
from backend.ai_service.schemas.sql import SQLGenerationResponse
from backend.ai_service.services.llm_provider import TextGenerationClient, get_llm_client_and_model
from backend.ai_service.services.metadata_retriever import MetadataRetriever
from backend.ai_service.services.schema_context import DATABASE_SCHEMA_CONTEXT
from backend.ai_service.services.sql_validator import SQLValidator
from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class SQLGenerator:
    def __init__(
        self,
        metadata_retriever: MetadataRetriever,
        ollama_client: TextGenerationClient | None = None,
        llm_client: TextGenerationClient | None = None,
        validator: SQLValidator | None = None,
    ) -> None:
        self.metadata_retriever = metadata_retriever
        self.llm_client = llm_client or ollama_client
        self.validator = validator or SQLValidator()

    def generate(self, question: str) -> SQLGenerationResponse:
        return self._generate(question=question, correction_context=None)

    def generate_with_feedback(
        self,
        question: str,
        failed_sql: str,
        execution_error: str,
    ) -> SQLGenerationResponse:
        correction_context = (
            "The previous SQL was rejected by PostgreSQL. "
            "Generate a corrected PostgreSQL SELECT query.\n\n"
            f"Previous SQL:\n{failed_sql}\n\n"
            f"PostgreSQL error:\n{execution_error}\n\n"
            "Fix table names, column names, aliases, and join keys using only the database schema. "
            "Return only corrected SQL."
        )
        return self._generate(question=question, correction_context=correction_context)

    def _generate(
        self,
        question: str,
        correction_context: str | None,
    ) -> SQLGenerationResponse:
        settings = get_settings()
        logger.info(
            "sql_generation.start question=%r provider=%s correction=%s",
            question,
            settings.llm_provider,
            bool(correction_context),
        )
        metadata = self.metadata_retriever.search(
            query=question,
            limit=settings.sql_generation_metadata_limit,
        )
        logger.info(
            "sql_generation.metadata_context count=%s context=%s",
            len(metadata),
            [
                {
                    "table": item.table,
                    "column": item.column,
                    "business_name": item.business_name,
                    "score": item.score,
                }
                for item in metadata
            ],
        )
        prompt = self._build_prompt(
            question=question,
            metadata=metadata,
            correction_context=correction_context,
        )
        llm_client, model = self._get_llm_client_and_model()
        logger.info(
            "sql_generation.llm_request provider=%s model=%s prompt_chars=%s",
            settings.llm_provider,
            model,
            len(prompt),
        )
        raw_response = llm_client.generate(model=model, prompt=prompt)
        logger.info("sql_generation.llm_response raw_response=%r", raw_response)
        sql = self._extract_sql(raw_response)
        logger.info("sql_generation.extracted_sql sql=%r", sql)
        validation = self.validator.validate(sql)
        logger.info(
            "sql_generation.validation is_valid=%s normalized_sql=%r reason=%r",
            validation.is_valid,
            validation.normalized_sql,
            validation.reason,
        )

        return SQLGenerationResponse(
            question=question,
            sql=validation.normalized_sql if validation.is_valid else sql,
            is_valid=validation.is_valid,
            validation_reason=validation.reason,
            metadata=[item.model_dump() for item in metadata],
        )

    def _get_llm_client_and_model(self) -> tuple[TextGenerationClient, str]:
        return get_llm_client_and_model(task="sql", client_override=self.llm_client)

    def _build_prompt(
        self,
        question: str,
        metadata: list[MetadataSearchResult],
        correction_context: str | None = None,
    ) -> str:
        metadata_lines = "\n".join(
            (
                f"- table={item.table}, column={item.column}, "
                f"name={item.business_name}, description={item.description}"
            )
            for item in metadata
        )
        correction_section = (
            f"""
Correction context:
{correction_context}
"""
            if correction_context
            else ""
        )
        question_hints = self._build_question_hints(question)
        return f"""
You generate PostgreSQL SELECT queries for an enterprise business database.

Rules:
- Return only SQL. No markdown. No explanation.
- Use only SELECT queries.
- Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, COPY, or comments.
- Prefer explicit joins.
- Use the database schema and schema metadata below as the source of truth.
- Use only tables and columns listed in the database schema.
- Use only the required join keys listed in the database schema.
- If a question says PO1001, match purchase_orders.po_number = 'PO1001'.
- If a question says MAT100, also consider material codes are stored like MAT0100.

Database schema:
{DATABASE_SCHEMA_CONTEXT}

Schema metadata:
{metadata_lines}

Question-specific deterministic hints:
{question_hints}

{correction_section}
Question:
{question}

SQL:
""".strip()

    def _extract_sql(self, text: str) -> str:
        fenced_match = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()
        return text.strip()

    def _build_question_hints(self, question: str) -> str:
        hints = []
        upper_question = question.upper()

        customer_codes = sorted(set(re.findall(r"\bCUST\d+\b", upper_question)))
        if customer_codes:
            hints.append(
                "- Customer code filter: join customers c ON sales_orders.customer_id = c.id "
                f"and filter c.code IN ({', '.join(repr(code) for code in customer_codes)})."
            )
            hints.append(
                "- For customer material/order questions, use sales_orders so, "
                "sales_order_items soi, materials m, and customers c."
            )
            hints.append(
                "- For customer quantity or committed/customer committed wording, use "
                "sales_order_items.order_qty AS quantity."
            )
            hints.append(
                "- Do not use sales_orders.code; that column does not exist. "
                "Do not use purchase_order_items.commit_qty for customer orders."
            )

        supplier_codes = sorted(set(re.findall(r"\bSUP\d+\b", upper_question)))
        if supplier_codes:
            hints.append(
                "- Supplier code filter: join suppliers s ON purchase_orders.supplier_id = s.id "
                f"and filter s.code IN ({', '.join(repr(code) for code in supplier_codes)})."
            )

        purchase_orders = sorted(set(re.findall(r"\bPO\d+\b", upper_question)))
        if purchase_orders:
            hints.append(
                "- Purchase order filter: use purchase_orders.po_number "
                f"IN ({', '.join(repr(po) for po in purchase_orders)})."
            )

        sales_orders = sorted(set(re.findall(r"\bSO\d+\b", upper_question)))
        if sales_orders:
            hints.append(
                "- Sales order filter: use sales_orders.so_number "
                f"IN ({', '.join(repr(so) for so in sales_orders)})."
            )

        materials = sorted(set(re.findall(r"\bMAT\d+\b", upper_question)))
        if materials:
            hints.append(
                "- Material code filter: join materials m and filter m.material_code "
                f"IN ({', '.join(repr(material) for material in materials)})."
            )

        if not hints:
            return "- No deterministic entity hints detected."

        return "\n".join(hints)
