import logging
import re
from typing import Protocol

from backend.ai_service.schemas.metadata import MetadataSearchResult
from backend.ai_service.schemas.sql import SQLGenerationResponse
from backend.ai_service.services.gemini_client import GeminiClient
from backend.ai_service.services.metadata_retriever import MetadataRetriever
from backend.ai_service.services.ollama_client import OllamaClient
from backend.ai_service.services.sql_validator import SQLValidator
from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class TextGenerationClient(Protocol):
    def generate(self, model: str, prompt: str) -> str: ...


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
        settings = get_settings()
        logger.info("sql_generation.start question=%r provider=%s", question, settings.llm_provider)
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
        prompt = self._build_prompt(question=question, metadata=metadata)
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
        settings = get_settings()
        if self.llm_client:
            return self.llm_client, settings.ollama_sql_model

        provider = settings.llm_provider.lower().strip()
        if provider == "gemini":
            return (
                GeminiClient(
                    api_key=settings.gemini_api_key or "",
                    base_url=settings.gemini_base_url,
                ),
                settings.gemini_model,
            )
        if provider == "ollama":
            return OllamaClient(settings.ollama_base_url), settings.ollama_sql_model

        raise ValueError("LLM_PROVIDER must be either 'ollama' or 'gemini'.")

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
