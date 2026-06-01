import logging

from backend.shared.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    for logger_name in (
        "backend.ai_service",
        "backend.ai_service.services.metadata_retriever",
        "backend.ai_service.services.sql_generator",
        "backend.ai_service.services.sql_executor",
    ):
        logging.getLogger(logger_name).setLevel(level)
