import json
import uuid

from app.db.executor import execute_query
from app.db.introspect import introspect_schema
from app.llm.prompts import SQL_GENERATION_SYSTEM_PROMPT, build_sql_generation_prompt
from app.llm.router import get_completion
from app.orchestrator.explainer import explain_result
from app.orchestrator.session_state import (
    build_clarification_context,
    create_session,
    get_session,
    store_clarifying_question,
    store_user_answer,
)
from app.schemas.sql_result import SQLGenerationResult


def _call_llm_for_sql(
    question: str,
    provider: str | None,
    clarification_context: str | None = None,
) -> SQLGenerationResult:
    schema = introspect_schema()
    schema_text = schema.to_prompt_string()

    prompt = build_sql_generation_prompt(schema_text, question, clarification_context)

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


def _execute_and_format(
    question: str, generation_result: SQLGenerationResult, provider: str | None
) -> dict:
    execution_result = execute_query(generation_result.sql)

    assumptions_dicts = [a.model_dump() for a in generation_result.assumptions]

    explanation = explain_result(
        question=question,
        sql=generation_result.sql,
        assumptions=assumptions_dicts,
        columns=execution_result["columns"],
        rows=execution_result["rows"],
        row_count=execution_result["row_count"],
        truncated=execution_result["truncated"],
        provider=provider,
    )

    return {
        "question": question,
        "status": "ready",
        "reasoning": generation_result.reasoning,
        "assumptions": assumptions_dicts,
        "overall_confidence": generation_result.overall_confidence,
        "generated_sql": generation_result.sql,
        "columns": execution_result["columns"],
        "rows": execution_result["rows"],
        "row_count": execution_result["row_count"],
        "truncated": execution_result["truncated"],
        "explanation": {
            "summary": explanation.summary,
            "assumptions_stated": explanation.assumptions_stated,
            "caveats": explanation.caveats,
        },
    }


def run_pipeline(question: str, provider: str | None = None) -> dict:
    generation_result = _call_llm_for_sql(question, provider)

    if generation_result.status == "needs_clarification":
        session_id = str(uuid.uuid4())
        create_session(session_id, question)
        store_clarifying_question(
            session_id,
            generation_result.clarifying_question.question,
            generation_result.clarifying_question.options,
        )
        return {
            "question": question,
            "status": "needs_clarification",
            "session_id": session_id,
            "clarifying_question": generation_result.clarifying_question.question,
            "options": generation_result.clarifying_question.options,
            "reasoning": generation_result.reasoning,
            "assumptions": [a.model_dump() for a in generation_result.assumptions],
        }

    return _execute_and_format(question, generation_result, provider)


def continue_with_clarification(
    session_id: str, user_answer: str, provider: str | None = None
) -> dict:
    store_user_answer(session_id, user_answer)
    context = build_clarification_context(session_id)
    original_question = get_session(session_id)["original_question"]

    generation_result = _call_llm_for_sql(
        original_question, provider, clarification_context=context
    )

    if generation_result.status == "needs_clarification":
        return {
            "question": original_question,
            "status": "still_ambiguous",
            "reasoning": generation_result.reasoning,
            "assumptions": [a.model_dump() for a in generation_result.assumptions],
        }

    return _execute_and_format(original_question, generation_result, provider)