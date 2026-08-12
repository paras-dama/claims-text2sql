from pydantic import BaseModel, Field


class ResultExplanation(BaseModel):
    summary: str = Field(
        description="1-3 sentence plain-English answer to the user's question"
    )
    assumptions_stated: list[str] = Field(
        default_factory=list,
        description="Plain-language restatement of any assumptions made, even minor ones",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Any data quality notes, e.g. zero results, null values, truncation",
    )