from fastapi import APIRouter, HTTPException

from backend.ai_service.schemas.sql import (
    SQLExecutionRequest,
    SQLExecutionResponse,
    SQLValidationRequest,
    SQLValidationResponse,
)
from backend.ai_service.services.sql_executor import SQLExecutionError, SQLExecutor
from backend.ai_service.services.sql_validator import SQLValidator

router = APIRouter()


@router.post("/validate", response_model=SQLValidationResponse)
def validate_sql(request: SQLValidationRequest) -> SQLValidationResponse:
    result = SQLValidator().validate(request.sql)
    return SQLValidationResponse(**result.model_dump())


@router.post("/execute", response_model=SQLExecutionResponse)
def execute_sql(request: SQLExecutionRequest) -> SQLExecutionResponse:
    try:
        return SQLExecutor().execute(sql=request.sql, limit=request.limit)
    except SQLExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
