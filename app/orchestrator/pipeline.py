import json

from app.db.executor import execute_query
from app.db.introspect import introspect_schema
from app.llm.prompts import SQL_GENERATION_SYSTEM_PROMPT, build_sql_generation_prompt
from app.llm.router import get_completion
from app.schemas.sql_result import SQLGenerationResult


def generate_sql(question: str, provider: str | None = None) -> SQLGenerationResult:
    schema = introspect_schema()
    schema_text = schema.to_prompt_string()

    prompt = build_sql_generation_prompt(schema_text, question)

    raw_response = get_completion(
        prompt=prompt,
        system_prompt=SQL_GENERATION_SYSTEM_PROMPT,
        provider=provider,
    )

    # The LLM is instructed to return only JSON, but models sometimes
    # wrap it in markdown fences anyway. Strip those defensively.
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    parsed = json.loads(cleaned)
    return SQLGenerationResult(**parsed)


def run_pipeline(question: str, provider: str | None = None) -> dict:
    """
    Full pipeline: question -> SQL -> execution -> results.
    NOTE: no SQL safety validation yet (Step 6). Only call this with
    trusted/test questions until guardrails are added.
    """
    generation_result = generate_sql(question, provider=provider)
    execution_result = execute_query(generation_result.sql)

    return {
        "question": question,
        "generated_sql": generation_result.sql,
        "reasoning": generation_result.reasoning,
        "columns": execution_result["columns"],
        "rows": execution_result["rows"],
        "row_count": execution_result["row_count"],
        "truncated": execution_result["truncated"],
    }