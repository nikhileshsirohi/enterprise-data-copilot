FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8001

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements/base.txt

COPY backend backend
COPY pyproject.toml pyproject.toml
COPY data/company_policies data/company_policies

RUN mkdir -p data/company_policies \
    && chown -R app:app /app

USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/v1/health/', timeout=3).read()" || exit 1

CMD ["sh", "-c", "uvicorn backend.ai_service.main:app --host 0.0.0.0 --port ${PORT}"]
