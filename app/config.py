from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    database_url_readonly: str
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    default_llm_provider: str = "groc"

    class Config:
        env_file = ".env"

settings = Settings()



