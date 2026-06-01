from fastapi import APIRouter, HTTPException

from backend.ai_service.schemas.ask import AskRequest, AskResponse
from backend.ai_service.services.metadata_retriever import get_metadata_retriever
from backend.ai_service.services.question_answerer import QuestionAnswerer
from backend.ai_service.services.sql_executor import SQLExecutionError
from backend.ai_service.services.sql_generator import SQLGenerator

router = APIRouter()


@router.post("/", response_model=AskResponse)
def ask_question(request: AskRequest) -> AskResponse:
    try:
        sql_generator = SQLGenerator(metadata_retriever=get_metadata_retriever())
        return QuestionAnswerer(sql_generator=sql_generator).ask(
            question=request.question,
            limit=request.limit,
        )
    except SQLExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ConnectionError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
