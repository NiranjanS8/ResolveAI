from typing import TypedDict, Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from app.models.base import TicketStatus, Intent


class TicketState(TypedDict):
    ticket_id: str
    customer_id: str
    subject: str
    body: str
    status: str
    intent: Optional[str]
    urgency: Optional[str]
    sentiment: Optional[str]
    confidence: Optional[str]
    routing_score: Optional[str]
    retrieved_context: Optional[List[Dict[str, Any]]]
    decision: Optional[str]
    draft_response: Optional[str]
    error: Optional[str]
    created_at: str
    updated_at: str