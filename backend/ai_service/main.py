from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.ai_service.api.v1.router import api_router
from backend.shared.config import get_settings
from backend.shared.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="Enterprise Data Copilot AI Service",
        version="0.1.0",
        debug=settings.app_debug,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=f"/api/{settings.api_version}")
    return app


app = create_app()
