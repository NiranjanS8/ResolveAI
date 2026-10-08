from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models.base import TicketStatus, Intent


class TicketCreate(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)


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