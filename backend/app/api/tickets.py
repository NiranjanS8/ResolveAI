from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.graphs import get_compiled_graph
from app.graphs.state import TicketState
from app.models.base import Ticket, TicketMessage, TicketStatus, AgentFeedback, AuditLog
from app.schemas.ticket import (
    TicketCreate,
    TicketResponse,
    TicketDetailResponse,
    TicketMessageCreate,
    TicketMessageResponse,
    AgentFeedbackCreate,
    AgentFeedbackResponse,
    RefundAction,
    OrderStatusAction,
    PasswordResetAction,
    EmailAction,
)
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/tickets", tags=["tickets"])

# Phase 7: Action constants in Indian Rupees (₹)
# 1 INR ≈ 0.012 USD, so $50 ≈ ₹4150, using ₹2000 as the cap for MVP
REFUND_INR_CAP = 2000  # ₹2000 cap (approx $24)
ACTIONS_ALLOWED = {"refund", "order_status", "password_reset"}
ALLOWED_CHANNELS = {"email", "chat"}

# Phase 10: Email processing constants
EMAIL_MAX_SIZE = 10 * 1024 * 1024  # 10MB max email size
EMAIL_REQUIRED_FIELDS = {"subject", "body", "from_address"}

# Phase 10: Security constants
RATE_LIMIT_PER_MINUTE = 60  # Max tickets per minute per customer


def run_ticket_graph(ticket: Ticket, agent_decision: str = None, edited_draft: str = None, action: str = None, action_amount: float = None) -> dict:
    import logging
    logger = logging.getLogger(__name__)
    try:
        graph = get_compiled_graph()
        initial_state: TicketState = {
            "ticket_id": str(ticket.id),
            "customer_id": ticket.customer_id,
            "subject": ticket.subject,
            "body": ticket.body,
            "status": ticket.status.value if hasattr(ticket.status, 'value') else str(ticket.status),
            "intent": ticket.intent,
            "urgency": ticket.urgency,
            "sentiment": ticket.sentiment,
            "confidence": ticket.confidence,
            "retrieved_context": ticket.retrieved_context if hasattr(ticket, 'retrieved_context') else None,
            "decision": None,
            "draft_response": None,
            "error": None,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else "",
        }
        
        # Apply agent decisions for resume
        if agent_decision == "approve" and edited_draft:
            # Agent approved and sent the draft
            initial_state["draft_response"] = edited_draft
            initial_state["status"] = "resolved"
        elif agent_decision == "edit" and edited_draft:
            # Agent edited the draft - use the edited version
            initial_state["draft_response"] = edited_draft
            initial_state["status"] = "draft_for_review"
        elif agent_decision == "reject":
            # Agent rejected the draft - escalate
            initial_state["decision"] = "escalate"
            initial_state["status"] = "escalated"
        
        # Phase 7: Action layer - tool calling with guardrails in INR
        if action and action in ACTIONS_ALLOWED:
            guardrail_violation = False
            action_payload = {}
            
            if action == "refund":
                # Guardrail: rupee cap enforcement
                if action_amount is not None and action_amount > REFUND_INR_CAP:
                    guardrail_violation = True
                    initial_state["decision"] = "draft_for_review"
                    initial_state["draft_response"] = f"""Refund request of ₹{action_amount} exceeds the ₹{REFUND_INR_CAP} cap.
This has been routed to human review for approval.
Please provide additional justification for the excess amount."""
                else:
                    # Successful refund under cap
                    action_payload = {
                        "refund_amount": action_amount,
                        "refund_currency": "INR",
                        "refund_status": "processed",
                    }
                    initial_state["status"] = "auto_resolved"
                    initial_state["decision"] = "auto_resolve"
                    # Log action to audit_log
                    async with AsyncSessionLocal() as audit_db:
                        from sqlalchemy import insert as sa_insert
                        await audit_db.execute(
                            sa_insert(AuditLog.__table__).values(
                                id=uuid4(),
                                ticket_id=ticket.id,
                                action="refund_executed",
                                payload=action_payload,
                                confidence=ticket.confidence,
                                executed_by="system",
                            )
                        )
                        await audit_db.commit()
            elif action == "order_status":
                # Allow-listed action: order status lookup
                action_payload = {
                    "action": "order_status_lookup",
                    "status": "shipped",
                    "estimated_delivery": "2024-12-20",
                }
                initial_state["status"] = "auto_resolved"
                initial_state["decision"] = "auto_resolve"
                # Log action to audit_log
                async with AsyncSessionLocal() as audit_db:
                    from sqlalchemy import insert as sa_insert
                    await audit_db.execute(
                        sa_insert(AuditLog.__table__).values(
                            id=uuid4(),
                            ticket_id=ticket.id,
                            action="order_status_checked",
                            payload=action_payload,
                            confidence=ticket.confidence,
                            executed_by="system",
                        )
                    )
                    await audit_db.commit()
            elif action == "password_reset":
                # Allow-listed action: password reset
                action_payload = {
                    "action": "password_reset_initiated",
                    "temp_password": "Temp@1234",
                    "reset_url": "https://resolveai.com/reset-password",
                }
                initial_state["status"] = "auto_resolved"
                initial_state["decision"] = "auto_resolve"
                # Log action to audit_log
                async with AsyncSessionLocal() as audit_db:
                    from sqlalchemy import insert as sa_insert
                    await audit_db.execute(
                        sa_insert(AuditLog.__table__).values(
                            id=uuid4(),
                            ticket_id=ticket.id,
                            action="password_reset_executed",
                            payload=action_payload,
                            confidence=ticket.confidence,
                            executed_by="system",
                        )
                    )
                    await audit_db.commit()
            
            # If guardrail violation for refund, don't execute action
            if guardrail_violation:
                initial_state["status"] = "draft_for_review"
                initial_state["decision"] = "draft_for_review"
        
        config = {"configurable": {"thread_id": str(ticket.id)}}
        
        # If we have a decision already, resume from where it left off
        if agent_decision in ("approve", "edit", "reject") or (action and action in ACTIONS_ALLOWED):
            # Resume the graph with the agent's decision
            result = graph.invoke(initial_state, config=config)
        else:
            # Fresh graph run
            result = graph.invoke(initial_state, config=config)
        
        logger.info(f"Graph result for ticket {ticket.id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Graph run failed for ticket {ticket.id}: {e}", exc_info=True)
        raise


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    ticket_in: TicketCreate,
    db: AsyncSession = Depends(get_db),
):
    # Phase 10: Validate channel
    if ticket_in.channel not in ALLOWED_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel. Allowed channels: {', '.join(ALLOWED_CHANNELS)}",
        )
    
    ticket = Ticket(
        id=uuid4(),
        customer_id=ticket_in.customer_id,
        subject=ticket_in.subject,
        body=ticket_in.body,
        status=TicketStatus.NEW,
        channel=ticket_in.channel,
    )
    db.add(ticket)

    # Add initial message from customer
    message = TicketMessage(
        id=uuid4(),
        ticket_id=ticket.id,
        role="customer",
        content=ticket_in.body,
    )
    db.add(message)

    await db.commit()
    await db.refresh(ticket)

    # Trigger graph run in a thread pool — run_ticket_graph is synchronous and
    # performs blocking LLM calls. Running it directly in this async route would
    # block the FastAPI event loop for the full LLM round-trip (3–10s).
    import asyncio
    try:
        result = await asyncio.to_thread(run_ticket_graph, ticket)
        print(f"GRAPH RESULT: {result}")
        # Update ticket with graph results
        if result.get("intent"):
            ticket.intent = result["intent"]
        if result.get("urgency"):
            ticket.urgency = result["urgency"]
        if result.get("sentiment"):
            ticket.sentiment = result["sentiment"]
        if result.get("confidence"):
            ticket.confidence = result["confidence"]
        if result.get("status"):
            ticket.status = TicketStatus(result["status"])
        await db.commit()
        await db.refresh(ticket)
    except Exception as e:
        # Log error but don't fail the request
        import logging
        logging.error(f"Graph run failed for ticket {ticket.id}: {e}")
        print(f"GRAPH ERROR: {e}")
        import traceback
        traceback.print_exc()

    return ticket


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket)
        .order_by(Ticket.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.messages))
        .where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/{ticket_id}/messages", response_model=TicketMessageResponse, status_code=status.HTTP_201_CREATED)
async def add_message(
    ticket_id: str,
    message_in: TicketMessageCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    message = TicketMessage(
        id=uuid4(),
        ticket_id=ticket.id,
        role=message_in.role,
        content=message_in.content,
        meta=message_in.meta,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


@router.post("/{ticket_id}/approve", response_model=TicketResponse)
async def approve_draft(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Agent approves the AI draft - ticket resolves end-to-end."""
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Run graph with approve decision
    result = run_ticket_graph(ticket, agent_decision="approve", edited_draft=ticket.draft_response)
    
    # Log agent feedback
    async with AsyncSessionLocal() as feedback_db:
        feedback = AgentFeedback(
            ticket_id=ticket.id,
            original_draft=ticket.draft_response or "",
            edited_response=ticket.draft_response or "",
            agent_id="agent_1",  # In production, use actual agent ID
        )
        feedback_db.add(feedback)
        await feedback_db.commit()
    
    # Also log to audit_log
    async with AsyncSessionLocal() as audit_db:
        from sqlalchemy import insert as sa_insert
        await audit_db.execute(
            sa_insert(AuditLog.__table__).values(
                id=uuid4(),
                ticket_id=ticket.id,
                action="draft_approved",
                payload={"draft": ticket.draft_response},
                confidence=ticket.confidence,
                executed_by="agent_1",
            )
        )
        await audit_db.commit()
    
    await db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/edit", response_model=TicketResponse)
async def edit_draft(
    ticket_id: str,
    edited_draft: str,
    db: AsyncSession = Depends(get_db),
):
    """Agent edits the AI draft before sending."""
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Run graph with edit decision and edited draft
    result = run_ticket_graph(ticket, agent_decision="edit", edited_draft=edited_draft)
    
    # Log agent feedback - original vs edited
    async with AsyncSessionLocal() as feedback_db:
        feedback = AgentFeedback(
            ticket_id=ticket.id,
            original_draft=ticket.draft_response or "",
            edited_response=edited_draft,
            agent_id="agent_1",  # In production, use actual agent ID
        )
        feedback_db.add(feedback)
        await feedback_db.commit()
    
    await db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/reject", response_model=TicketResponse)
async def reject_draft(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Agent rejects the AI draft - ticket escalates to human."""
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Run graph with reject decision
    result = run_ticket_graph(ticket, agent_decision="reject")
    
    # Log agent feedback
    async with AsyncSessionLocal() as feedback_db:
        feedback = AgentFeedback(
            ticket_id=ticket.id,
            original_draft=ticket.draft_response or "",
            edited_response=ticket.draft_response or "",
            agent_id="agent_1",  # In production, use actual agent ID
        )
        feedback_db.add(feedback)
        await feedback_db.commit()
    
    await db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/refund", response_model=TicketResponse)
async def process_refund(
    ticket_id: str,
    refund_action: RefundAction,
    db: AsyncSession = Depends(get_db),
):
    """Process a refund request with ₹2000 cap guardrail."""
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Run graph with refund action (INR cap enforced in guardrail)
    result = run_ticket_graph(ticket, action="refund", action_amount=refund_action.amount)
    
    await db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/order-status", response_model=TicketResponse)
async def check_order_status(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Check order status - allow-listed action."""
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Run graph with order_status action
    result = run_ticket_graph(ticket, action="order_status")
    
    await db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/password-reset", response_model=TicketResponse)
async def initiate_password_reset(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Initiate password reset - allow-listed action."""
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Run graph with password_reset action
    result = run_ticket_graph(ticket, action="password_reset")
    
    await db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/email", response_model=TicketResponse)
async def process_email(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Process an email-ticket - thread replies into existing tickets."""
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Phase 10: If ticket already exists, add message and re-run graph
    # If new email, create new ticket
    if ticket.channel == "email" and ticket.status in ("new", "open"):
        # Add email as a message to existing ticket
        from sqlalchemy import insert as sa_insert
        
        # Check for replies/references
        # In a full implementation, we'd parse email headers for threading
        # For MVP, just add a note that this is an email reply
        async with AsyncSessionLocal() as audit_db:
            await audit_db.execute(
                sa_insert(AuditLog.__table__).values(
                    id=uuid4(),
                    ticket_id=ticket.id,
                    action="email_reply_threaded",
                    payload={"note": "Email reply added to existing ticket"},
                    confidence=ticket.confidence,
                    executed_by="system",
                )
            )
            await audit_db.commit()
    
    await db.refresh(ticket)
    return ticket