from fastapi import FastAPI

from app.config import settings
from app.db.introspect import introspect_schema

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