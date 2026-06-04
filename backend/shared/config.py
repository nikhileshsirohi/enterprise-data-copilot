from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_secret_key: str = Field(alias="APP_SECRET_KEY")
    app_allowed_hosts: str = Field(default="localhost,127.0.0.1", alias="APP_ALLOWED_HOSTS")
    api_version: str = Field(default="v1", alias="API_VERSION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    postgres_db: str = Field(alias="POSTGRES_DB")
    postgres_user: str = Field(alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_semantic_cache_prefix: str = Field(
        default="semantic_cache:ask",
        alias="REDIS_SEMANTIC_CACHE_PREFIX",
    )
    redis_langgraph_state_prefix: str = Field(
        default="langgraph:ask",
        alias="REDIS_LANGGRAPH_STATE_PREFIX",
    )
    redis_chat_history_prefix: str = Field(
        default="chat:history",
        alias="REDIS_CHAT_HISTORY_PREFIX",
    )
    api_rate_limit_requests: int = Field(default=120, alias="API_RATE_LIMIT_REQUESTS")
    api_rate_limit_window_seconds: int = Field(default=60, alias="API_RATE_LIMIT_WINDOW_SECONDS")
    jwt_refresh_token_ttl_seconds: int = Field(
        default=604800,
        alias="JWT_REFRESH_TOKEN_TTL_SECONDS",
    )
    sql_execution_timeout_seconds: int = Field(default=10, alias="SQL_EXECUTION_TIMEOUT_SECONDS")
    sql_result_limit: int = Field(default=100, alias="SQL_RESULT_LIMIT")
    sql_generation_metadata_limit: int = Field(default=8, alias="SQL_GENERATION_METADATA_LIMIT")
    sql_generation_retry_count: int = Field(default=1, alias="SQL_GENERATION_RETRY_COUNT")
    chat_history_context_limit: int = Field(default=6, alias="CHAT_HISTORY_CONTEXT_LIMIT")
    chat_history_redis_ttl_seconds: int = Field(
        default=604800,
        alias="CHAT_HISTORY_REDIS_TTL_SECONDS",
    )
    langgraph_state_ttl_seconds: int = Field(default=86400, alias="LANGGRAPH_STATE_TTL_SECONDS")
    semantic_cache_enabled: bool = Field(default=True, alias="SEMANTIC_CACHE_ENABLED")
    semantic_cache_threshold: float = Field(default=0.95, alias="SEMANTIC_CACHE_THRESHOLD")
    semantic_cache_business_threshold: float = Field(
        default=0.90,
        alias="SEMANTIC_CACHE_BUSINESS_THRESHOLD",
    )
    semantic_cache_ttl_seconds: int = Field(default=86400, alias="SEMANTIC_CACHE_TTL_SECONDS")

    elasticsearch_url: str = Field(default="http://localhost:9200", alias="ELASTICSEARCH_URL")
    policy_documents_index: str = Field(
        default="company_policy_documents",
        alias="POLICY_DOCUMENTS_INDEX",
    )
    policy_documents_dir: str = Field(
        default="data/company_policies",
        alias="POLICY_DOCUMENTS_DIR",
    )
    policy_chunk_size: int = Field(default=900, alias="POLICY_CHUNK_SIZE")
    policy_chunk_overlap: int = Field(default=150, alias="POLICY_CHUNK_OVERLAP")
    policy_rag_min_score: float = Field(default=0.75, alias="POLICY_RAG_MIN_SCORE")
    policy_hybrid_candidate_multiplier: int = Field(
        default=4,
        alias="POLICY_HYBRID_CANDIDATE_MULTIPLIER",
    )
    intent_embedding_confidence_threshold: float = Field(
        default=0.78,
        alias="INTENT_EMBEDDING_CONFIDENCE_THRESHOLD",
    )
    intent_llm_fallback_enabled: bool = Field(default=True, alias="INTENT_LLM_FALLBACK_ENABLED")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_reasoning_model: str = Field(default="qwen2.5:14b", alias="OLLAMA_REASONING_MODEL")
    ollama_sql_model: str = Field(
        default="qwen2.5-coder:14b-instruct",
        alias="OLLAMA_SQL_MODEL",
    )
    ollama_embedding_model: str = Field(default="nomic-embed-text", alias="OLLAMA_EMBEDDING_MODEL")
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        alias="GEMINI_BASE_URL",
    )

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.app_allowed_hosts.split(",") if host.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
