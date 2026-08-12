from typing import Literal

from pydantic import BaseModel, Field


class Assumption(BaseModel):
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
    chosen_interpretation: str | None = Field(
        default=None,
        description="The interpretation used, if status is 'ready'. Null if still ambiguous and not yet decided.",
    )
    confidence: float = Field(ge=0, le=1)


class ClarifyingQuestion(BaseModel):
    question: str = Field(description="The question to show the user")
    options: list[str] = Field(
        default_factory=list,
        description="Short, concrete answer choices, e.g. specific interpretations",
    )


class SQLGenerationResult(BaseModel):
    status: Literal["ready", "needs_clarification"]
    sql: str | None = Field(default=None)
    reasoning: str = Field(description="Brief explanation of the approach taken")
    assumptions: list[Assumption] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0, le=1)
    clarifying_question: ClarifyingQuestion | None = Field(
        default=None,
        description="Present only when status is 'needs_clarification'",
    )