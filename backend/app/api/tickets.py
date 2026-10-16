from uuid import uuid4
import asyncio
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
from app.db.session import AsyncSessionLocal, SyncSessionLocal

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


def apply_graph_result(ticket: Ticket, result: dict) -> None:
    """Copy the relevant graph state fields back onto the ticket row."""
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
    if result.get("draft_response") is not None:
        ticket.draft_response = result["draft_response"]
    if result.get("retrieved_context") is not None:
        ticket.retrieved_context = result["retrieved_context"]


def log_audit_action(
    ticket_id,
    action: str,
    payload: dict,
    confidence=None,
    executed_by: str = "system",
) -> None:
    """Write an audit_log row via a sync session (used from synchronous graph code)."""
    from sqlalchemy import insert as sa_insert
    with SyncSessionLocal() as audit_db:
        audit_db.execute(
            sa_insert(AuditLog.__table__).values(
                id=uuid4(),
                ticket_id=ticket_id,
                action=action,
                payload=payload,
                confidence=confidence,
                executed_by=executed_by,
            )
        )
        audit_db.commit()


def _initial_state(ticket: Ticket) -> TicketState:
    return {
        "ticket_id": str(ticket.id),
        "customer_id": ticket.customer_id,
        "subject": ticket.subject,
        "body": ticket.body,
        "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        "intent": ticket.intent,
        "urgency": ticket.urgency,
        "sentiment": ticket.sentiment,
        "confidence": ticket.confidence,
        "retrieved_context": ticket.retrieved_context,
        "decision": None,
        "draft_response": None,
        "error": None,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else "",
    }


def _graph_config(ticket: Ticket) -> dict:
    return {"configurable": {"thread_id": str(ticket.id)}}


def _state_after_run(graph, config: dict, fallback: dict) -> dict:
    """Return the persisted graph state, falling back to the invoke result."""
    snapshot = graph.get_state(config)
    if snapshot is not None and snapshot.values:
        return dict(snapshot.values)
    return dict(fallback)


def run_ticket_graph(ticket: Ticket) -> dict:
    """Run the graph for a new ticket.

    Returns the state at completion, or at the human-in-the-loop interrupt when
    the ticket is routed to draft_for_review (where the run stays paused until
    resumed via resume_ticket_graph).
    """
    graph = get_compiled_graph()
    config = _graph_config(ticket)
    result = graph.invoke(_initial_state(ticket), config=config)
    return _state_after_run(graph, config, result)


def resume_ticket_graph(ticket: Ticket, action: str, edited_draft: str | None = None) -> dict:
    """Resume a paused draft_for_review run with the agent's decision."""
    graph = get_compiled_graph()
    config = _graph_config(ticket)
    review: dict = {"action": action}
    if edited_draft is not None:
        review["edited_response"] = edited_draft
    result = graph.invoke(Command(resume=review), config=config)
    return _state_after_run(graph, config, result)


def execute_action(ticket: Ticket, action: str, amount: float | None = None) -> dict:
    """Run an allow-listed action with code-enforced guardrails.

    Guardrails are enforced in code, not just prompted: only allow-listed
    actions run, the refund cap is a hard limit, and a cap breach routes the
    ticket to human review instead of executing.
    """
    if action not in ACTIONS_ALLOWED:
        raise HTTPException(status_code=400, detail=f"Action not allow-listed: {action}")

    if action == "refund":
        if amount is not None and amount > REFUND_INR_CAP:
            log_audit_action(
                ticket.id,
                "guardrail_violation",
                {"action": "refund", "requested": amount, "cap": REFUND_INR_CAP},
                ticket.confidence,
            )
            return {
                "status": "draft_for_review",
                "decision": "draft_for_review",
                "draft_response": (
                    f"Refund request of ₹{amount} exceeds the ₹{REFUND_INR_CAP} cap. "
                    "Routed to human review for approval."
                ),
            }
        payload = {"refund_amount": amount, "refund_currency": "INR", "refund_status": "processed"}
        log_audit_action(ticket.id, "refund_executed", payload, ticket.confidence)
        return {
            "status": "auto_resolved",
            "decision": "auto_resolve",
            "draft_response": f"Refund of ₹{amount} processed successfully.",
        }

    if action == "order_status":
        log_audit_action(
            ticket.id, "order_status_checked", {"action": "order_status_lookup"}, ticket.confidence
        )
        return {
            "status": "auto_resolved",
            "decision": "auto_resolve",
            "draft_response": "Order status retrieved and shared with the customer.",
        }

    log_audit_action(
        ticket.id, "password_reset_executed", {"action": "password_reset_initiated"}, ticket.confidence
    )
    return {
        "status": "auto_resolved",
        "decision": "auto_resolve",
        "draft_response": "Password reset link dispatched to the customer.",
    }


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
    try:
        result = await asyncio.to_thread(run_ticket_graph, ticket)
        print(f"GRAPH RESULT: {result}")
        # Update ticket with graph results
        apply_graph_result(ticket, result)
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
    
    original_draft = ticket.draft_response or ""

    # Resume the paused graph with the agent's approval
    result = await asyncio.to_thread(resume_ticket_graph, ticket, "approve")
    apply_graph_result(ticket, result)
    final_response = result.get("draft_response") or original_draft

    if final_response:
        db.add(TicketMessage(id=uuid4(), ticket_id=ticket.id, role="agent", content=final_response))

    # Capture the agent decision for the feedback loop
    db.add(AgentFeedback(
        ticket_id=ticket.id,
        original_draft=original_draft,
        edited_response=final_response,
        agent_id="agent_1",  # In production, use actual agent ID
    ))
    log_audit_action(
        ticket.id, "draft_approved", {"draft": final_response}, ticket.confidence, executed_by="agent_1"
    )

    await db.commit()
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
    
    original_draft = ticket.draft_response or ""

    # Resume the paused graph with the agent's edited response
    result = await asyncio.to_thread(resume_ticket_graph, ticket, "edit", edited_draft)
    apply_graph_result(ticket, result)
    final_response = result.get("draft_response") or edited_draft

    if final_response:
        db.add(TicketMessage(id=uuid4(), ticket_id=ticket.id, role="agent", content=final_response))

    # Capture original draft vs. the agent's final version for the feedback loop
    db.add(AgentFeedback(
        ticket_id=ticket.id,
        original_draft=original_draft,
        edited_response=final_response,
        agent_id="agent_1",  # In production, use actual agent ID
    ))
    log_audit_action(
        ticket.id, "draft_edited", {"draft": final_response}, ticket.confidence, executed_by="agent_1"
    )

    await db.commit()
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
    
    # Resume the paused graph with the agent's rejection
    result = await asyncio.to_thread(resume_ticket_graph, ticket, "reject")
    apply_graph_result(ticket, result)

    db.add(AgentFeedback(
        ticket_id=ticket.id,
        original_draft=ticket.draft_response or "",
        edited_response="",
        agent_id="agent_1",  # In production, use actual agent ID
    ))
    log_audit_action(
        ticket.id, "draft_rejected", {"draft": ticket.draft_response}, ticket.confidence, executed_by="agent_1"
    )

    await db.commit()
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
    
    # Execute refund action with the ₹2000 cap guardrail enforced in code
    result = execute_action(ticket, "refund", refund_action.amount)
    apply_graph_result(ticket, result)

    await db.commit()
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
    
    # Execute allow-listed order status lookup
    result = execute_action(ticket, "order_status")
    apply_graph_result(ticket, result)

    await db.commit()
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
    
    # Execute allow-listed password reset
    result = execute_action(ticket, "password_reset")
    apply_graph_result(ticket, result)

    await db.commit()
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