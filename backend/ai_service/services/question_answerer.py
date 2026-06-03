import json
import logging

from backend.ai_service.schemas.ask import AskResponse
from backend.ai_service.schemas.sql import SQLExecutionResponse, SQLGenerationResponse
from backend.ai_service.services.ask_workflow import (
    LangGraphAskWorkflow,
    SQLExecutorProtocol,
    SQLGeneratorProtocol,
)
from backend.ai_service.services.chat_history import ChatContextMessage
from backend.ai_service.services.llm_provider import TextGenerationClient, get_llm_client_and_model
from backend.ai_service.services.sql_executor import SQLExecutor
from backend.ai_service.services.workflow_state_store import RedisWorkflowStateStore
from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class QuestionAnswerer:
    def __init__(
        self,
        sql_generator: SQLGeneratorProtocol,
        sql_executor: SQLExecutorProtocol | None = None,
        llm_client: TextGenerationClient | None = None,
        state_store: RedisWorkflowStateStore | None = None,
    ) -> None:
        self.sql_generator = sql_generator
        self.sql_executor = sql_executor or SQLExecutor()
        self.llm_client = llm_client
        self.state_store = state_store

    def ask(
        self,
        question: str,
        limit: int | None = None,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> AskResponse:
        settings = get_settings()
        context = chat_context or []
        logger.info(
            "ask.start question=%r provider=%s chat_context_messages=%s",
            question,
            settings.llm_provider,
            len(context),
        )
        workflow = LangGraphAskWorkflow(
            sql_generator=self.sql_generator,
            sql_executor=self.sql_executor,
            answer_summarizer=self._summarize,
            state_store=self.state_store,
        )
        return workflow.run(question=question, limit=limit, chat_context=context)

    def _summarize(
        self,
        question: str,
        generation: SQLGenerationResponse,
        execution: SQLExecutionResponse,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> str:
        llm_client, model = get_llm_client_and_model(
            task="reasoning",
            client_override=self.llm_client,
        )
        prompt = self._build_answer_prompt(
            question=question,
            generation=generation,
            execution=execution,
            chat_context=chat_context or [],
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
        chat_context: list[ChatContextMessage],
    ) -> str:
        payload = {
            "question": question,
            "chat_context": [
                {"role": message.role, "content": message.content}
                for message in chat_context
            ],
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
Use recent conversation context only to understand follow-up wording.
Do not invent facts.
If rows are empty, say that no matching data was found.
If truncated is true, mention that the answer is based on the returned limited rows.
Keep the answer concise and business friendly.

SQL result JSON:
{json.dumps(payload, indent=2)}

Answer:
""".strip()
