from pydantic import BaseModel, Field


class SQLGenerationResult(BaseModel):
    sql: str = Field(description="The generated SQL SELECT query")
    reasoning: str = Field(description="Brief explanation of what the query does")