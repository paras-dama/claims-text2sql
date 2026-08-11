"""
Dynamic table discovery: instead of a maintained allowlist, this queries
Postgres directly for every table in the 'public' schema, then excludes
a short denylist of infrastructure tables (things this project's own
pipeline created for itself, not real domain data).

RESULT: adding a new domain table to the database (policy, coverages,
person_info, etc.) requires NO changes to this file, or to
introspect.py, sql_guard.py, or retriever.py. Create the table in
Postgres and it's automatically introspected, validated, embeddable,
and queryable on the next request.

Safety note: this is a denylist model (expose everything except X),
appropriate for a single-user local project. A production/multi-tenant
version would likely use an explicit allowlist or row-level security
instead — see evals/notes.md for this noted as a known scoping decision.
"""

import psycopg

from app.config import settings

# Tables that exist in this database but are NOT domain data — created
# by this project's own pipeline for its own purposes (e.g. Step 9's
# pgvector embeddings table). Never expose these to the LLM as
# queryable tables.
DENYLIST = {
    "schema_embeddings",
}


def get_allowed_tables() -> list[str]:
    """
    Returns every table in the 'public' schema, minus DENYLIST.
    Called fresh each time (not cached) so newly created tables are
    picked up immediately without restarting the app.
    """
    conn = psycopg.connect(settings.database_url)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    all_tables = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()

    return [t for t in all_tables if t not in DENYLIST]