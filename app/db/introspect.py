import psycopg

from app.config import settings
from app.schemas.db_schema import ColumnInfo, SchemaInfo, TableInfo

# Only introspect tables we actually want the LLM to know about.
# This is an intentional allowlist — it's also your first real
# guardrail: the LLM will never even see tables outside this list.
ALLOWED_TABLES = ["claims", "claim_reserves"]


def get_primary_keys(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a
            ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = %s::regclass AND i.indisprimary
        """,
        (table_name,),
    )
    return {row[0] for row in cur.fetchall()}


def get_foreign_keys(cur, table_name: str) -> dict[str, tuple[str, str]]:
    """Returns {column_name: (referenced_table, referenced_column)}"""
    cur.execute(
        """
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = %s
        """,
        (table_name,),
    )
    return {row[0]: (row[1], row[2]) for row in cur.fetchall()}


def get_column_comments(cur, table_name: str) -> dict[str, str]:
    cur.execute(
        """
        SELECT a.attname, pgd.description
        FROM pg_catalog.pg_statio_all_tables st
        JOIN pg_catalog.pg_description pgd ON pgd.objoid = st.relid
        JOIN pg_catalog.pg_attribute a
            ON a.attrelid = st.relid AND a.attnum = pgd.objsubid
        WHERE st.relname = %s
        """,
        (table_name,),
    )
    return {row[0]: row[1] for row in cur.fetchall() if row[1]}


def introspect_table(cur, table_name: str) -> TableInfo:
    primary_keys = get_primary_keys(cur, table_name)
    foreign_keys = get_foreign_keys(cur, table_name)
    comments = get_column_comments(cur, table_name)

    cur.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )

    columns = []
    for col_name, data_type, is_nullable in cur.fetchall():
        fk_target = foreign_keys.get(col_name)
        columns.append(
            ColumnInfo(
                name=col_name,
                data_type=data_type,
                is_nullable=(is_nullable == "YES"),
                is_primary_key=col_name in primary_keys,
                is_foreign_key=fk_target is not None,
                references_table=fk_target[0] if fk_target else None,
                references_column=fk_target[1] if fk_target else None,
                column_comment=comments.get(col_name),
            )
        )

    return TableInfo(table_name=table_name, columns=columns)


def introspect_schema() -> SchemaInfo:
    conn = psycopg.connect(settings.database_url)
    cur = conn.cursor()

    tables = [introspect_table(cur, name) for name in ALLOWED_TABLES]

    cur.close()
    conn.close()
    return SchemaInfo(tables=tables)