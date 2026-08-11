import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.validation.sql_guard import SQLValidationError, validate_and_prepare_sql

# Hard safety limit — no query returns more than this many rows,
# regardless of what the LLM generated. Prevents accidentally
# dumping huge result sets.
MAX_ROWS = 200


def execute_query(sql: str) -> dict:
    """
    Validates SQL via sqlglot-based guardrails, then executes it against
    Postgres using a connection scoped to a read-only role's permissions
    at the SQL level (see 6.7 for the actual read-only DB role setup).
    """
    safe_sql = validate_and_prepare_sql(sql)

    conn = psycopg.connect(settings.database_url_readonly, row_factory=dict_row)
    cur = conn.cursor()

    # Statement timeout: abort any query that runs longer than 5 seconds.
    cur.execute("SET statement_timeout = '5s'")
    cur.execute(safe_sql)
    rows = cur.fetchmany(MAX_ROWS)
    column_names = [desc[0] for desc in cur.description] if cur.description else []

    cur.close()
    conn.close()

    return {
        "columns": column_names,
        "rows": rows,
        "row_count": len(rows),
        "truncated": len(rows) == MAX_ROWS,
        "executed_sql": safe_sql,
    }