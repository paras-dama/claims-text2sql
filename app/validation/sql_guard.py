import sqlglot
from sqlglot import exp

# Must match ALLOWED_TABLES in app/db/introspect.py — this is intentional
# duplication for now (two places listing the same tables). We'll note
# this as a small piece of tech debt to revisit if the project grows.
ALLOWED_TABLES = {"claims", "claim_reserves"}

MAX_ROWS_LIMIT = 200


class SQLValidationError(Exception):
    """Raised when generated SQL fails a safety check."""


def validate_and_prepare_sql(sql: str) -> str:
    """
    Parses and validates generated SQL. Raises SQLValidationError if
    anything looks unsafe. Returns a (possibly modified) safe SQL string
    if validation passes.
    """
    sql = sql.strip().rstrip(";")

    try:
        parsed_statements = sqlglot.parse(sql, read="postgres")
    except Exception as e:
        raise SQLValidationError(f"SQL failed to parse: {e}")

    # Reject statement stacking (e.g. "SELECT ...; DROP TABLE ...;")
    if len(parsed_statements) != 1:
        raise SQLValidationError(
            f"Expected exactly one SQL statement, found {len(parsed_statements)}."
        )

    statement = parsed_statements[0]
    if statement is None:
        raise SQLValidationError("SQL parsed to an empty statement.")

    # Only SELECT is allowed — reject INSERT, UPDATE, DELETE, DROP,
    # ALTER, CREATE, TRUNCATE, and anything else.
    if not isinstance(statement, exp.Select):
        raise SQLValidationError(
            f"Only SELECT statements are allowed. Got: {type(statement).__name__}"
        )

    # Check every table referenced anywhere in the query (including
    # subqueries and CTEs) against our allowlist.
    referenced_tables = {
        table.name.lower() for table in statement.find_all(exp.Table)
    }
    disallowed = referenced_tables - ALLOWED_TABLES
    if disallowed:
        raise SQLValidationError(
            f"Query references disallowed table(s): {disallowed}. "
            f"Allowed tables: {ALLOWED_TABLES}"
        )

    # Reject any data-modifying subquery constructs sqlglot might parse
    # as part of a SELECT tree in edge cases (defense in depth).
    forbidden_node_types = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter)
    for node in statement.walk():
        if isinstance(node[0], forbidden_node_types):
            raise SQLValidationError(
                f"Query contains forbidden operation: {type(node[0]).__name__}"
            )

    # Enforce a LIMIT if none exists and this isn't a pure aggregate
    # query (aggregates like COUNT/SUM naturally return one row).
    has_limit = statement.args.get("limit") is not None
    is_aggregate_only = _is_likely_single_row_aggregate(statement)

    if not has_limit and not is_aggregate_only:
        statement = statement.limit(MAX_ROWS_LIMIT)
    elif has_limit:
        # Cap an existing LIMIT so the LLM can't set LIMIT 100000
        existing_limit = statement.args["limit"]
        try:
            limit_value = int(existing_limit.expression.this)
            if limit_value > MAX_ROWS_LIMIT:
                statement = statement.limit(MAX_ROWS_LIMIT)
        except (AttributeError, ValueError):
            # If we can't confidently parse the limit value, force our own
            statement = statement.limit(MAX_ROWS_LIMIT)

    return statement.sql(dialect="postgres")


def _is_likely_single_row_aggregate(statement: exp.Select) -> bool:
    """
    Heuristic: if there's no GROUP BY and every selected expression is
    an aggregate function (COUNT, SUM, AVG, MIN, MAX) or a literal,
    the query returns exactly one row and doesn't need a LIMIT.
    """
    if statement.args.get("group"):
        return False  # GROUP BY can return many rows, needs a limit

    aggregate_funcs = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)
    expressions = statement.expressions

    if not expressions:
        return False

    for expression in expressions:
        contains_aggregate = any(
            isinstance(node[0], aggregate_funcs) for node in expression.walk()
        )
        if not contains_aggregate:
            return False

    return True