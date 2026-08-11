import psycopg

from app.config import settings
from app.schemas.db_schema import ColumnInfo, SchemaInfo, TableInfo
from app.domain_tables import get_allowed_tables

# Only fetch sample values for columns whose type suggests they're
# categorical/enum-like. Sampling a BIGINT PK or a TIMESTAMP wastes a
# query and adds no useful signal.
SAMPLEABLE_TYPES = {"character varying", "text", "character"}

MAX_SAMPLE_VALUES = 5


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


def get_sample_values(cur, table_name: str, column_name: str) -> list[str]:
    """
    Returns up to MAX_SAMPLE_VALUES distinct real values from this
    column. This is what prevents the LLM from guessing casing/format
    for status/code-like columns instead of matching real stored data.
    """
    query = f"""
        SELECT DISTINCT {column_name}
        FROM {table_name}
        WHERE {column_name} IS NOT NULL
        LIMIT {MAX_SAMPLE_VALUES}
    """
    cur.execute(query)
    return [str(row[0]) for row in cur.fetchall()]


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

        sample_values = []
        if data_type in SAMPLEABLE_TYPES and col_name not in primary_keys:
            sample_values = get_sample_values(cur, table_name, col_name)

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
                sample_values=sample_values,
            )
        )

    return TableInfo(table_name=table_name, columns=columns)


def introspect_schema() -> SchemaInfo:
    allowed_tables = get_allowed_tables()

    conn = psycopg.connect(settings.database_url)
    cur = conn.cursor()

    tables = [introspect_table(cur, name) for name in allowed_tables]

    cur.close()
    conn.close()
    return SchemaInfo(tables=tables)