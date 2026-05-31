import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.shared.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    safe_postgres_dsn = settings.postgres_dsn.replace(settings.postgres_password, "********")

    print("Environment configuration loaded")
    print(f"APP_ENV={settings.app_env}")
    print(f"API_VERSION={settings.api_version}")
    print(f"POSTGRES_DSN={safe_postgres_dsn}")
    print(f"REDIS_URL={settings.redis_url}")
    print(f"ELASTICSEARCH_URL={settings.elasticsearch_url}")
    print(f"OLLAMA_BASE_URL={settings.ollama_base_url}")


if __name__ == "__main__":
    main()
