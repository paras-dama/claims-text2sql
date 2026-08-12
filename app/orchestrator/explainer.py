import json

from app.llm.prompts import RESULT_EXPLANATION_SYSTEM_PROMPT, build_explanation_prompt
from app.llm.router import get_completion
from app.schemas.explanation import ResultExplanation


def explain_result(
    question: str,
    sql: str,
    assumptions: list[dict],
    columns: list[str],
    rows: list[dict],
    row_count: int,
    truncated: bool,
    provider: str | None = None,
) -> ResultExplanation:
    prompt = build_explanation_prompt(
        question, sql, assumptions, columns, rows, row_count, truncated
    )

    raw_response = get_completion(
        prompt=prompt,
        system_prompt=RESULT_EXPLANATION_SYSTEM_PROMPT,
        provider=provider,
        temperature=0.3,  # slightly higher than SQL gen — this is prose, not precision-critical syntax
    )

    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    parsed = json.loads(cleaned)
    return ResultExplanation(**parsed)