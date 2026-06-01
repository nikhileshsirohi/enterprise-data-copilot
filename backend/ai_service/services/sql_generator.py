import re

from backend.ai_service.schemas.metadata import MetadataSearchResult
from backend.ai_service.schemas.sql import SQLGenerationResponse
from backend.ai_service.services.metadata_retriever import MetadataRetriever
from backend.ai_service.services.ollama_client import OllamaClient
from backend.ai_service.services.sql_validator import SQLValidator
from backend.shared.config import get_settings


class SQLGenerator:
    def __init__(
        self,
        metadata_retriever: MetadataRetriever,
        ollama_client: OllamaClient | None = None,
        validator: SQLValidator | None = None,
    ) -> None:
        self.metadata_retriever = metadata_retriever
        self.ollama_client = ollama_client
        self.validator = validator or SQLValidator()

    def generate(self, question: str) -> SQLGenerationResponse:
        settings = get_settings()
        metadata = self.metadata_retriever.search(
            query=question,
            limit=settings.sql_generation_metadata_limit,
        )
        prompt = self._build_prompt(question=question, metadata=metadata)
        ollama_client = self.ollama_client or OllamaClient(settings.ollama_base_url)
        raw_response = ollama_client.generate(model=settings.ollama_sql_model, prompt=prompt)
        sql = self._extract_sql(raw_response)
        validation = self.validator.validate(sql)

        return SQLGenerationResponse(
            question=question,
            sql=validation.normalized_sql if validation.is_valid else sql,
            is_valid=validation.is_valid,
            validation_reason=validation.reason,
            metadata=[item.model_dump() for item in metadata],
        )

    def _build_prompt(self, question: str, metadata: list[MetadataSearchResult]) -> str:
        metadata_lines = "\n".join(
            (
                f"- table={item.table}, column={item.column}, "
                f"name={item.business_name}, description={item.description}"
            )
            for item in metadata
        )
        return f"""
You generate PostgreSQL SELECT queries for an enterprise business database.

Rules:
- Return only SQL. No markdown. No explanation.
- Use only SELECT queries.
- Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, COPY, or comments.
- Prefer explicit joins.
- Use the schema metadata below as the source of truth.
- If a question says PO1001, match purchase_orders.po_number = 'PO1001'.
- If a question says MAT100, also consider material codes are stored like MAT0100.

Schema metadata:
{metadata_lines}

Question:
{question}

SQL:
""".strip()

    def _extract_sql(self, text: str) -> str:
        fenced_match = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()
        return text.strip()
