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
    Full pipeline: question -> ambiguity check -> SQL (if ready) -> execution.
    If status is "needs_clarification", no SQL is executed — this just
    surfaces the ambiguity for now. Step 8 adds the actual clarification
    dialogue loop on top of this.
    """
    generation_result = generate_sql(question, provider=provider)

    response = {
        "question": question,
        "status": generation_result.status,
        "reasoning": generation_result.reasoning,
        "assumptions": [a.model_dump() for a in generation_result.assumptions],
        "overall_confidence": generation_result.overall_confidence,
    }

    if generation_result.status == "needs_clarification":
        response["generated_sql"] = None
        return response

    execution_result = execute_query(generation_result.sql)
    response.update({
        "generated_sql": generation_result.sql,
        "columns": execution_result["columns"],
        "rows": execution_result["rows"],
        "row_count": execution_result["row_count"],
        "truncated": execution_result["truncated"],
    })
    return response