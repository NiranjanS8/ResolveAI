from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models.base import TicketStatus, Intent, AgentFeedback


class AgentFeedbackCreate(BaseModel):
    original_draft: str = Field(..., min_length=1, description="The original AI draft before agent edits")
    edited_response: str = Field(..., min_length=1, description="The agent's final version of the response")
    agent_id: str = Field(..., min_length=1, max_length=100, description="Identifier of the agent who made the edit")


class AgentFeedbackResponse(AgentFeedbackCreate):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class TicketCreate(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    channel: str = Field(default="chat", min_length=1, max_length=50, description="Ticket channel: 'email' or 'chat'")


class TicketMessageCreate(BaseModel):
    role: str = Field(..., min_length=1, max_length=50)
    content: str = Field(..., min_length=1)
    meta: Optional[dict] = None


class TicketMessageResponse(BaseModel):
    id: UUID
    ticket_id: UUID
    role: str
    content: str
    meta: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class TicketResponse(BaseModel):
    id: UUID
    customer_id: str
    subject: str
    body: str
    status: TicketStatus
    intent: Optional[Intent]
    urgency: Optional[str]
    sentiment: Optional[str]
    confidence: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TicketDetailResponse(TicketResponse):
    messages: list[TicketMessageResponse] = []


# Phase 7: Action schemas with INR (Indian Rupees) instead of USD
class RefundAction(BaseModel):
    amount: float = Field(..., gt=0, description="Refund amount in Indian Rupees (₹)")


class OrderStatusAction(BaseModel):
    pass


class PasswordResetAction(BaseModel):
    pass


class ActionResult(BaseModel):
    success: bool = Field(description="Whether the action was successfully executed")
    message: str = Field(description="Description of the action result")
    amount: Optional[float] = Field(None, description="Amount in INR if applicable")
    action: str = Field(description="Name of the action executed")


# Phase 10: Email action schema
class EmailAction(BaseModel):
    recipient: str = Field(..., min_length=1, max_length=255, description="Email address recipient")
    subject: str = Field(..., min_length=1, max_length=500, description="Email subject")
    body: str = Field(..., min_length=1, description="Email body content")
    thread_ticket_id: Optional[str] = Field(
        default=None, 
        description="Existing ticket ID to thread reply into (for email threading)"
    )