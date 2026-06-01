from fastapi import APIRouter, HTTPException

from backend.ai_service.schemas.ask import AskRequest, AskResponse
from backend.ai_service.services.chat_history import ChatHistoryRecorder, ChatPersistenceError
from backend.ai_service.services.metadata_retriever import get_metadata_retriever
from backend.ai_service.services.question_answerer import QuestionAnswerer
from backend.ai_service.services.sql_executor import SQLExecutionError
from backend.ai_service.services.sql_generator import SQLGenerator

router = APIRouter()


@router.post("/", response_model=AskResponse)
def ask_question(request: AskRequest) -> AskResponse:
    try:
        sql_generator = SQLGenerator(metadata_retriever=get_metadata_retriever())
        response = QuestionAnswerer(sql_generator=sql_generator).ask(
            question=request.question,
            limit=request.limit,
        )
        if request.persist:
            persistence = ChatHistoryRecorder().record_exchange(
                user_id=request.user_id,
                session_id=request.session_id,
                question=request.question,
                answer=response,
                limit=request.limit,
            )
            response = response.model_copy(
                update={
                    "persisted": persistence.persisted,
                    "session_id": persistence.session_id,
                    "user_message_id": persistence.user_message_id,
                    "assistant_message_id": persistence.assistant_message_id,
                }
            )
        return response
    except ChatPersistenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ConnectionError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
