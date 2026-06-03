from fastapi import APIRouter

from backend.ai_service.api.v1.routes import ask, health, metadata, sql, workflows

api_router = APIRouter()
api_router.include_router(ask.router, prefix="/ask", tags=["ask"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(metadata.router, prefix="/metadata", tags=["metadata"])
api_router.include_router(sql.router, prefix="/sql", tags=["sql"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
