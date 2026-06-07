from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ai_service_dockerfile_has_production_runtime_defaults() -> None:
    dockerfile = (ROOT / "backend" / "ai_service" / "Dockerfile").read_text()

    assert "FROM python:3.13-slim AS runtime" in dockerfile
    assert "pip install --no-cache-dir -r requirements/base.txt" in dockerfile
    assert "USER app" in dockerfile
    assert "EXPOSE 8001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "uvicorn backend.ai_service.main:app --host 0.0.0.0 --port ${PORT}" in dockerfile


def test_dockerignore_excludes_local_secrets_and_build_noise() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text().splitlines()

    assert ".env" in dockerignore
    assert ".venv" in dockerignore
    assert "__pycache__" in dockerignore
    assert "node_modules" in dockerignore
    assert "!.env.example" in dockerignore
