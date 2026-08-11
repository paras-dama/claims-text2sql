from typing import Literal

from pydantic import BaseModel, Field


class Assumption(BaseModel):
    """
    One specific interpretation choice the LLM made (or is asking about).
    """
    ambiguity_type: Literal[
        "metric_definition",
        "status_filter",
        "category_aggregation",
        "time_basis",
        "other",
    ]
    description: str = Field(
        description="Plain-English description of what's ambiguous here"
    )
    chosen_interpretation: str = Field(
        description="The interpretation that was used (or would be used) to generate SQL"
    )
    confidence: float = Field(ge=0, le=1)


class SQLGenerationResult(BaseModel):
    status: Literal["ready", "needs_clarification"]
    sql: str | None = Field(
        default=None,
        description="Generated SQL. Present only if status is 'ready'.",
    )
    reasoning: str = Field(description="Brief explanation of the approach taken")
    assumptions: list[Assumption] = Field(
        default_factory=list,
        description="Any interpretation choices made, even if status is 'ready'",
    )
    overall_confidence: float = Field(ge=0, le=1)