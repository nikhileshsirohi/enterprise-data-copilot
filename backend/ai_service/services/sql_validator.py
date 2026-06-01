import re

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import DDL, DML, Keyword

from backend.ai_service.schemas.sql import SQLValidationResponse


class SQLValidator:
    forbidden_keywords = {
        "ALTER",
        "ANALYZE",
        "CALL",
        "COPY",
        "CREATE",
        "DELETE",
        "DROP",
        "EXEC",
        "EXECUTE",
        "GRANT",
        "INSERT",
        "MERGE",
        "REFRESH",
        "REINDEX",
        "REVOKE",
        "TRUNCATE",
        "UPDATE",
        "VACUUM",
    }
    forbidden_patterns = (
        re.compile(r"--"),
        re.compile(r"/\*"),
        re.compile(r"\*/"),
        re.compile(r"\bpg_sleep\s*\(", re.IGNORECASE),
    )

    def validate(self, sql: str) -> SQLValidationResponse:
        normalized_sql = sqlparse.format(sql.strip(), strip_comments=True).strip()
        if not normalized_sql:
            return SQLValidationResponse(is_valid=False, reason="SQL is empty.")

        if self._has_forbidden_pattern(sql):
            return SQLValidationResponse(
                is_valid=False,
                reason="SQL contains comments or unsafe function patterns.",
            )

        statements = [statement for statement in sqlparse.parse(normalized_sql) if statement.tokens]
        if len(statements) != 1:
            return SQLValidationResponse(
                is_valid=False,
                reason="Only one SQL statement is allowed.",
            )

        statement = statements[0]
        if statement.get_type() != "SELECT":
            return SQLValidationResponse(
                is_valid=False,
                reason="Only SELECT statements are allowed.",
            )

        forbidden_keyword = self._find_forbidden_keyword(statement)
        if forbidden_keyword:
            return SQLValidationResponse(
                is_valid=False,
                reason=f"Forbidden SQL keyword detected: {forbidden_keyword}.",
            )

        if normalized_sql.endswith(";"):
            normalized_sql = normalized_sql[:-1].strip()

        return SQLValidationResponse(is_valid=True, normalized_sql=normalized_sql)

    def _has_forbidden_pattern(self, sql: str) -> bool:
        return any(pattern.search(sql) for pattern in self.forbidden_patterns)

    def _find_forbidden_keyword(self, statement: Statement) -> str | None:
        for token in statement.flatten():
            if token.ttype in (DML, DDL, Keyword):
                value = token.value.upper()
                if value in self.forbidden_keywords:
                    return value
        return None
