from backend.shared.config import get_settings


def test_settings_load_from_environment() -> None:
    settings = get_settings()

    assert settings.app_env == "local"
    assert settings.postgres_db == "enterprise_data_copilot"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.elasticsearch_url == "http://localhost:9200"
    assert settings.allowed_hosts == ["localhost", "127.0.0.1"]
    assert settings.api_rate_limit_requests == 120
    assert settings.api_rate_limit_window_seconds == 60
    assert settings.sql_execution_timeout_seconds == 10
    assert settings.sql_result_limit == 100
