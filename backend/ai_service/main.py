from fastapi import FastAPI

from backend.ai_service.api.v1.router import api_router
from backend.shared.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Enterprise Data Copilot AI Service",
        version="0.1.0",
        debug=settings.app_debug,
    )
    app.include_router(api_router, prefix=f"/api/{settings.api_version}")
    return app


app = create_app()
