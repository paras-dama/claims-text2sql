import psycopg
from psycopg.rows import dict_row

from app.config import settings

# Hard safety limit — no query returns more than this many rows,
# regardless of what the LLM generated. Prevents accidentally
# dumping huge result sets.
MAX_ROWS = 200


def execute_query(sql: str) -> dict:
    """
    Executes a SQL query against Postgres and returns rows + metadata.
    Uses a plain connection for now — Step 6 adds real safety guardrails
    (read-only enforcement, SELECT-only checks, timeouts) before this
    is safe to expose to arbitrary LLM-generated SQL. Right now we are
    only running our own crafted test queries.
    """
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    cur = conn.cursor()

    cur.execute(sql)
    rows = cur.fetchmany(MAX_ROWS)
    column_names = [desc[0] for desc in cur.description] if cur.description else []

    cur.close()
    conn.close()

    return {
        "columns": column_names,
        "rows": rows,
        "row_count": len(rows),
        "truncated": len(rows) == MAX_ROWS,
    }