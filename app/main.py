from fastapi import FastAPI
from pydantic import BaseModel

from app.config import settings
from app.db.introspect import introspect_schema
from app.orchestrator.pipeline import continue_with_clarification, run_pipeline

app = FastAPI(title="Claims Text-to-SQL API")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "default_llm_provider": settings.default_llm_provider,
    }


@app.get("/schema")
def get_schema():
    schema = introspect_schema()
    return {
        "tables": [t.table_name for t in schema.tables],
        "prompt_representation": schema.to_prompt_string(),
    }


class QueryRequest(BaseModel):
    question: str
    provider: str | None = None


@app.post("/query")
def query(request: QueryRequest):
    return run_pipeline(request.question, provider=request.provider)


class ClarificationAnswerRequest(BaseModel):
    session_id: str
    answer: str
    provider: str | None = None


@app.post("/clarify")
def clarify(request: ClarificationAnswerRequest):
    return continue_with_clarification(
        request.session_id, request.answer, provider=request.provider
    )