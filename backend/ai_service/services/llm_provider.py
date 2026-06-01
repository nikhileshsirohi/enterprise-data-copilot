from typing import Literal, Protocol

from backend.ai_service.services.gemini_client import GeminiClient
from backend.ai_service.services.ollama_client import OllamaClient
from backend.shared.config import get_settings


class TextGenerationClient(Protocol):
    def generate(self, model: str, prompt: str) -> str: ...


def get_llm_client_and_model(
    task: Literal["sql", "reasoning"],
    client_override: TextGenerationClient | None = None,
) -> tuple[TextGenerationClient, str]:
    settings = get_settings()
    if client_override:
        model = settings.ollama_sql_model if task == "sql" else settings.ollama_reasoning_model
        return client_override, model

    provider = settings.llm_provider.lower().strip()
    if provider == "gemini":
        return (
            GeminiClient(
                api_key=settings.gemini_api_key or "",
                base_url=settings.gemini_base_url,
            ),
            settings.gemini_model,
        )
    if provider == "ollama":
        model = settings.ollama_sql_model if task == "sql" else settings.ollama_reasoning_model
        return OllamaClient(settings.ollama_base_url), model

    raise ValueError("LLM_PROVIDER must be either 'ollama' or 'gemini'.")
