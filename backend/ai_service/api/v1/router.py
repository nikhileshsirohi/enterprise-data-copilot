from fastapi import APIRouter

from backend.ai_service.api.v1.routes import health, metadata, sql

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(metadata.router, prefix="/metadata", tags=["metadata"])
api_router.include_router(sql.router, prefix="/sql", tags=["sql"])
