import json
import logging
from typing import Protocol

from backend.ai_service.schemas.ask import AskResponse
from backend.ai_service.schemas.sql import SQLExecutionResponse, SQLGenerationResponse
from backend.ai_service.services.llm_provider import TextGenerationClient, get_llm_client_and_model
from backend.ai_service.services.sql_executor import SQLExecutionError, SQLExecutor
from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class SQLGeneratorProtocol(Protocol):
    def generate(self, question: str) -> SQLGenerationResponse: ...

    def generate_with_feedback(
        self,
        question: str,
        failed_sql: str,
        execution_error: str,
    ) -> SQLGenerationResponse: ...


class SQLExecutorProtocol(Protocol):
    def execute(self, sql: str, limit: int | None = None) -> SQLExecutionResponse: ...


class QuestionAnswerer:
    def __init__(
        self,
        sql_generator: SQLGeneratorProtocol,
        sql_executor: SQLExecutorProtocol | None = None,
        llm_client: TextGenerationClient | None = None,
    ) -> None:
        self.sql_generator = sql_generator
        self.sql_executor = sql_executor or SQLExecutor()
        self.llm_client = llm_client

    def ask(self, question: str, limit: int | None = None) -> AskResponse:
        settings = get_settings()
        logger.info("ask.start question=%r provider=%s", question, settings.llm_provider)
        generation = self.sql_generator.generate(question)
        retry_count = 0
        max_retries = settings.sql_generation_retry_count

        while True:
            logger.info(
                "ask.sql_generation_done is_valid=%s sql=%r reason=%r retry_count=%s",
                generation.is_valid,
                generation.sql,
                generation.validation_reason,
                retry_count,
            )

            if not generation.is_valid or not generation.sql:
                answer = (
                    "I could not generate a safe read-only SQL query for this question. "
                    f"Reason: {generation.validation_reason or 'unknown'}"
                )
                logger.info("ask.stop_before_execution answer=%r", answer)
                return AskResponse(
                    question=question,
                    answer=answer,
                    sql=generation.sql,
                    is_sql_valid=False,
                    validation_reason=generation.validation_reason,
                    columns=[],
                    rows=[],
                    row_count=0,
                    truncated=False,
                    metadata=generation.metadata,
                    retry_count=retry_count,
                )

            try:
                execution = self.sql_executor.execute(sql=generation.sql, limit=limit)
                break
            except SQLExecutionError as exc:
                if retry_count >= max_retries:
                    answer = (
                        "I generated a safe read-only SQL query, but the database rejected it. "
                        "This usually means the model used a wrong table or column name. "
                        f"Error: {exc}"
                    )
                    logger.info("ask.execution_failed answer=%r", answer)
                    return AskResponse(
                        question=question,
                        answer=answer,
                        sql=generation.sql,
                        is_sql_valid=True,
                        validation_reason=None,
                        columns=[],
                        rows=[],
                        row_count=0,
                        truncated=False,
                        metadata=generation.metadata,
                        execution_error=str(exc),
                        retry_count=retry_count,
                    )

                retry_count += 1
                logger.info(
                    "ask.sql_execution_failed_retrying retry_count=%s max_retries=%s error=%s",
                    retry_count,
                    max_retries,
                    exc,
                )
                generation = self.sql_generator.generate_with_feedback(
                    question=question,
                    failed_sql=generation.sql,
                    execution_error=str(exc),
                )
        logger.info(
            "ask.sql_execution_done row_count=%s truncated=%s columns=%s",
            execution.row_count,
            execution.truncated,
            execution.columns,
        )
        answer = self._summarize(question=question, generation=generation, execution=execution)
        logger.info("ask.complete answer=%r", answer)

        return AskResponse(
            question=question,
            answer=answer,
            sql=execution.sql,
            is_sql_valid=True,
            validation_reason=None,
            columns=execution.columns,
            rows=execution.rows,
            row_count=execution.row_count,
            truncated=execution.truncated,
            metadata=generation.metadata,
            retry_count=retry_count,
        )

    def _summarize(
        self,
        question: str,
        generation: SQLGenerationResponse,
        execution: SQLExecutionResponse,
    ) -> str:
        llm_client, model = get_llm_client_and_model(
            task="reasoning",
            client_override=self.llm_client,
        )
        prompt = self._build_answer_prompt(
            question=question,
            generation=generation,
            execution=execution,
        )
        settings = get_settings()
        logger.info(
            "ask.answer_llm_request provider=%s model=%s prompt_chars=%s",
            settings.llm_provider,
            model,
            len(prompt),
        )
        raw_answer = llm_client.generate(model=model, prompt=prompt).strip()
        logger.info("ask.answer_llm_response raw_answer=%r", raw_answer)
        return raw_answer

    def _build_answer_prompt(
        self,
        question: str,
        generation: SQLGenerationResponse,
        execution: SQLExecutionResponse,
    ) -> str:
        payload = {
            "question": question,
            "sql": execution.sql,
            "columns": execution.columns,
            "row_count": execution.row_count,
            "truncated": execution.truncated,
            "rows": execution.rows,
            "metadata": generation.metadata,
        }
        return f"""
You are an enterprise data copilot.

Use only the SQL result JSON below to answer the user's question.
Do not invent facts.
If rows are empty, say that no matching data was found.
If truncated is true, mention that the answer is based on the returned limited rows.
Keep the answer concise and business friendly.

SQL result JSON:
{json.dumps(payload, indent=2)}

Answer:
""".strip()
