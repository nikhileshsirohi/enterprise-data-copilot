import logging
from collections.abc import Callable
from typing import Protocol, TypedDict

from langgraph.graph import END, StateGraph

from backend.ai_service.schemas.ask import AskResponse
from backend.ai_service.schemas.sql import SQLExecutionResponse, SQLGenerationResponse
from backend.ai_service.services.chat_history import ChatContextMessage
from backend.ai_service.services.sql_executor import SQLExecutionError
from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class SQLGeneratorProtocol(Protocol):
    def generate(
        self,
        question: str,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> SQLGenerationResponse: ...

    def generate_with_feedback(
        self,
        question: str,
        failed_sql: str,
        execution_error: str,
        chat_context: list[ChatContextMessage] | None = None,
    ) -> SQLGenerationResponse: ...


class SQLExecutorProtocol(Protocol):
    def execute(self, sql: str, limit: int | None = None) -> SQLExecutionResponse: ...


class AskWorkflowState(TypedDict, total=False):
    question: str
    limit: int | None
    chat_context: list[ChatContextMessage]
    max_retries: int
    retry_count: int
    generation: SQLGenerationResponse
    execution: SQLExecutionResponse
    failed_sql: str
    execution_error: str
    should_retry: bool
    response: AskResponse


AnswerSummarizer = Callable[
    [str, SQLGenerationResponse, SQLExecutionResponse, list[ChatContextMessage]],
    str,
]


class LangGraphAskWorkflow:
    def __init__(
        self,
        *,
        sql_generator: SQLGeneratorProtocol,
        sql_executor: SQLExecutorProtocol,
        answer_summarizer: AnswerSummarizer,
    ) -> None:
        self.sql_generator = sql_generator
        self.sql_executor = sql_executor
        self.answer_summarizer = answer_summarizer
        self.graph = self._build_graph()

    def run(
        self,
        *,
        question: str,
        limit: int | None,
        chat_context: list[ChatContextMessage],
    ) -> AskResponse:
        settings = get_settings()
        initial_state: AskWorkflowState = {
            "question": question,
            "limit": limit,
            "chat_context": chat_context,
            "max_retries": settings.sql_generation_retry_count,
            "retry_count": 0,
            "should_retry": False,
        }
        final_state = self.graph.invoke(initial_state)
        return final_state["response"]

    def _build_graph(self):
        graph = StateGraph(AskWorkflowState)
        graph.add_node("generate_sql", self._generate_sql)
        graph.add_node("execute_sql", self._execute_sql)
        graph.add_node("build_invalid_response", self._build_invalid_response)
        graph.add_node("build_execution_error_response", self._build_execution_error_response)
        graph.add_node("summarize_answer", self._summarize_answer)

        graph.set_entry_point("generate_sql")
        graph.add_conditional_edges(
            "generate_sql",
            self._route_after_generation,
            {
                "execute_sql": "execute_sql",
                "build_invalid_response": "build_invalid_response",
            },
        )
        graph.add_conditional_edges(
            "execute_sql",
            self._route_after_execution,
            {
                "generate_sql": "generate_sql",
                "build_execution_error_response": "build_execution_error_response",
                "summarize_answer": "summarize_answer",
            },
        )
        graph.add_edge("build_invalid_response", END)
        graph.add_edge("build_execution_error_response", END)
        graph.add_edge("summarize_answer", END)
        return graph.compile()

    def _generate_sql(self, state: AskWorkflowState) -> AskWorkflowState:
        question = state["question"]
        chat_context = state.get("chat_context", [])
        retry_count = state.get("retry_count", 0)
        execution_error = state.get("execution_error")
        failed_sql = state.get("failed_sql")

        logger.info("ask.workflow.generate_sql retry_count=%s", retry_count)
        if retry_count and execution_error and failed_sql:
            generation = self.sql_generator.generate_with_feedback(
                question=question,
                failed_sql=failed_sql,
                execution_error=execution_error,
                chat_context=chat_context,
            )
        else:
            generation = self.sql_generator.generate(question, chat_context=chat_context)

        logger.info(
            "ask.workflow.sql_generated is_valid=%s sql=%r reason=%r",
            generation.is_valid,
            generation.sql,
            generation.validation_reason,
        )
        return {
            "generation": generation,
            "should_retry": False,
            "execution_error": "",
            "failed_sql": "",
        }

    def _route_after_generation(self, state: AskWorkflowState) -> str:
        generation = state["generation"]
        if not generation.is_valid or not generation.sql:
            return "build_invalid_response"
        return "execute_sql"

    def _execute_sql(self, state: AskWorkflowState) -> AskWorkflowState:
        generation = state["generation"]
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 0)

        try:
            execution = self.sql_executor.execute(
                sql=generation.sql or "",
                limit=state.get("limit"),
            )
            logger.info(
                "ask.workflow.sql_executed row_count=%s truncated=%s",
                execution.row_count,
                execution.truncated,
            )
            return {
                "execution": execution,
                "should_retry": False,
                "execution_error": "",
                "failed_sql": "",
            }
        except SQLExecutionError as exc:
            should_retry = retry_count < max_retries
            logger.info(
                "ask.workflow.sql_execution_failed retry_count=%s max_retries=%s retry=%s error=%s",
                retry_count,
                max_retries,
                should_retry,
                exc,
            )
            return {
                "execution_error": str(exc),
                "failed_sql": generation.sql or "",
                "retry_count": retry_count + 1 if should_retry else retry_count,
                "should_retry": should_retry,
            }

    def _route_after_execution(self, state: AskWorkflowState) -> str:
        if state.get("execution") is not None:
            return "summarize_answer"
        if state.get("should_retry"):
            return "generate_sql"
        return "build_execution_error_response"

    def _build_invalid_response(self, state: AskWorkflowState) -> AskWorkflowState:
        generation = state["generation"]
        answer = (
            "I could not generate a safe read-only SQL query for this question. "
            f"Reason: {generation.validation_reason or 'unknown'}"
        )
        logger.info("ask.workflow.invalid_sql answer=%r", answer)
        return {
            "response": AskResponse(
                question=state["question"],
                answer=answer,
                sql=generation.sql,
                is_sql_valid=False,
                validation_reason=generation.validation_reason,
                columns=[],
                rows=[],
                row_count=0,
                truncated=False,
                metadata=generation.metadata,
                retry_count=state.get("retry_count", 0),
                used_chat_context=bool(state.get("chat_context", [])),
                chat_context_message_count=len(state.get("chat_context", [])),
            )
        }

    def _build_execution_error_response(self, state: AskWorkflowState) -> AskWorkflowState:
        generation = state["generation"]
        execution_error = state.get("execution_error", "")
        answer = (
            "I generated a safe read-only SQL query, but the database rejected it. "
            "This usually means the model used a wrong table or column name. "
            f"Error: {execution_error}"
        )
        logger.info("ask.workflow.execution_error answer=%r", answer)
        return {
            "response": AskResponse(
                question=state["question"],
                answer=answer,
                sql=generation.sql,
                is_sql_valid=True,
                validation_reason=None,
                columns=[],
                rows=[],
                row_count=0,
                truncated=False,
                metadata=generation.metadata,
                execution_error=execution_error,
                retry_count=state.get("retry_count", 0),
                used_chat_context=bool(state.get("chat_context", [])),
                chat_context_message_count=len(state.get("chat_context", [])),
            )
        }

    def _summarize_answer(self, state: AskWorkflowState) -> AskWorkflowState:
        answer = self.answer_summarizer(
            state["question"],
            state["generation"],
            state["execution"],
            state.get("chat_context", []),
        )
        logger.info("ask.workflow.complete answer=%r", answer)
        execution = state["execution"]
        generation = state["generation"]
        return {
            "response": AskResponse(
                question=state["question"],
                answer=answer,
                sql=execution.sql,
                is_sql_valid=True,
                validation_reason=None,
                columns=execution.columns,
                rows=execution.rows,
                row_count=execution.row_count,
                truncated=execution.truncated,
                metadata=generation.metadata,
                retry_count=state.get("retry_count", 0),
                used_chat_context=bool(state.get("chat_context", [])),
                chat_context_message_count=len(state.get("chat_context", [])),
            )
        }
