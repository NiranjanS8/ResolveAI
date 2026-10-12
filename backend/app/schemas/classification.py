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