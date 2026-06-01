from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row

from backend.ai_service.schemas.sql import SQLExecutionResponse
from backend.ai_service.services.sql_validator import SQLValidator
from backend.shared.config import get_settings


class SQLExecutionError(ValueError):
    pass


class SQLExecutor:
    def __init__(self, validator: SQLValidator | None = None) -> None:
        self.validator = validator or SQLValidator()

    def execute(self, sql: str, limit: int | None = None) -> SQLExecutionResponse:
        settings = get_settings()
        validation = self.validator.validate(sql)
        if not validation.is_valid or not validation.normalized_sql:
            raise SQLExecutionError(validation.reason or "SQL validation failed.")

        effective_limit = limit or settings.sql_result_limit
        safe_sql = self._apply_limit(validation.normalized_sql, effective_limit + 1)
        timeout_ms = int(settings.sql_execution_timeout_seconds * 1000)

        with closing(connect(settings.postgres_dsn, row_factory=dict_row)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
                cursor.execute(safe_sql)
                raw_rows = cursor.fetchall()
                columns = [column.name for column in cursor.description or []]

        truncated = len(raw_rows) > effective_limit
        rows = raw_rows[:effective_limit]

        return SQLExecutionResponse(
            sql=validation.normalized_sql,
            columns=columns,
            rows=[self._serialize_row(row) for row in rows],
            row_count=len(rows),
            truncated=truncated,
        )

    def _apply_limit(self, sql: str, limit: int) -> str:
        if " limit " in f" {sql.lower()} ":
            return sql
        return f"{sql} LIMIT {limit}"

    def _serialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {key: self._serialize_value(value) for key, value in row.items()}

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, date | datetime):
            return value.isoformat()
        return value
