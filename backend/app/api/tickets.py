from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.base import Ticket, TicketMessage, TicketStatus
from app.schemas.ticket import (
    TicketCreate,
    TicketResponse,
    TicketDetailResponse,
    TicketMessageCreate,
    TicketMessageResponse,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


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