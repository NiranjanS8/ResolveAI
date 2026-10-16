from pydantic import BaseModel, Field
from typing import Literal


class ClassificationOutput(BaseModel):
    intent: Literal[
        "general",
        "billing",
        "technical",
        "account",
        "refund",
        "order_status",
        "password_reset",
        "cancellation",
    ] = Field(description="Primary intent category")
    urgency: Literal["low", "medium", "high", "critical"] = Field(description="Urgency level")
    sentiment: Literal["negative", "neutral", "positive"] = Field(description="Customer sentiment")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence in classification")
    reasoning: str = Field(description="Brief explanation for the classification")


class DraftOutput(BaseModel):
    """Structured output for the drafter: the reply body and nothing else."""

    body: str = Field(
        description=(
            "The complete reply that will be sent to the customer. "
            "Plain text only: no Markdown, no emojis."
        )
    )
