from fastapi import FastAPI

from app.config import settings

app = FastAPI(title = "Claim Text To SQL API")

@app.get("/health")
def health_check():
    return {
        "status" : "ok",
        "defualt_llm_provider" : settings.default_llm_provider,
    }