from backend.shared.config import get_settings


def test_settings_load_from_environment() -> None:
    settings = get_settings()

    assert settings.app_env == "local"
    assert settings.postgres_db == "enterprise_data_copilot"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.redis_semantic_cache_prefix == "semantic_cache:ask"
    assert settings.redis_langgraph_state_prefix == "langgraph:ask"
    assert settings.redis_chat_history_prefix == "chat:history"
    assert settings.elasticsearch_url == "http://localhost:9200"
    assert settings.allowed_hosts == ["localhost", "127.0.0.1"]
    assert settings.api_rate_limit_requests == 120
    assert settings.api_rate_limit_window_seconds == 60
    assert settings.sql_execution_timeout_seconds == 10
    assert settings.sql_result_limit == 100
    assert settings.sql_generation_metadata_limit == 8
    assert settings.sql_generation_retry_count == 1
    assert settings.chat_history_context_limit == 6
    assert settings.chat_history_redis_ttl_seconds == 604800
    assert settings.langgraph_state_ttl_seconds == 86400
    assert settings.semantic_cache_enabled is True
    assert settings.semantic_cache_threshold == 0.95
    assert settings.semantic_cache_business_threshold == 0.90
    assert settings.semantic_cache_ttl_seconds == 86400
    assert settings.llm_provider in {"ollama", "gemini"}
    assert settings.gemini_model == "gemini-2.5-flash"
