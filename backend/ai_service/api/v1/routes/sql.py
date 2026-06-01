from fastapi import APIRouter

from backend.ai_service.schemas.sql import SQLValidationRequest, SQLValidationResponse
from backend.ai_service.services.sql_validator import SQLValidator

router = APIRouter()


@router.post("/validate", response_model=SQLValidationResponse)
def validate_sql(request: SQLValidationRequest) -> SQLValidationResponse:
    result = SQLValidator().validate(request.sql)
    return SQLValidationResponse(**result.model_dump())
