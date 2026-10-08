from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.graphs import get_compiled_graph
from app.graphs.state import TicketState
from app.models.base import Ticket, TicketMessage, TicketStatus
from app.schemas.ticket import (
    TicketCreate,
    TicketResponse,
    TicketDetailResponse,
    TicketMessageCreate,
    TicketMessageResponse,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


def run_ticket_graph(ticket: Ticket) -> dict:
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
            "intent": None,
            "urgency": None,
            "sentiment": None,
            "confidence": None,
            "retrieved_context": None,
            "decision": None,
            "draft_response": None,
            "error": None,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else "",
        }
        logger.info(f"Running graph for ticket {ticket.id}")
        config = {"configurable": {"thread_id": str(ticket.id)}}
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
    ticket = Ticket(
        id=uuid4(),
        customer_id=ticket_in.customer_id,
        subject=ticket_in.subject,
        body=ticket_in.body,
        status=TicketStatus.NEW,
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

    # Trigger graph run
    try:
        result = run_ticket_graph(ticket)
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