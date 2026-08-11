from fastapi import FastAPI
from pydantic import BaseModel

from app.config import settings
from app.db.introspect import introspect_schema
from app.llm.router import get_completion
from app.llm.prompts import BASIC_SYSTEM_PROMPT

app = FastAPI(title = "Claim Text To SQL API")

@app.get("/health")
def health_check():
    return {
        "status" : "ok",
        "defualt_llm_provider" : settings.default_llm_provider,
    }

@app.get("/schema")
def get_schema():
    schema = introspect_schema()
    return {
        "tables": [t.table_name for t in schema.tables],
        "prompt_representation": schema.to_prompt_string(),
    }

class PromptRequest(BaseModel):
    prompt: str
    provider: str | None = None


@app.post("/llm-test")
def llm_test(request: PromptRequest):
    response = get_completion(
        prompt=request.prompt,
        system_prompt=BASIC_SYSTEM_PROMPT,
        provider=request.provider,
    )
    return {"response": response}