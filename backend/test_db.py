import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from uuid import uuid4
from app.db.session import AsyncSessionLocal
from app.models.base import Ticket, TicketMessage, TicketStatus

async def test_create_ticket():
    async with AsyncSessionLocal() as db:
        try:
            ticket = Ticket(
                id=uuid4(),
                customer_id="cust_123",
                subject="Test ticket",
                body="This is a test ticket body",
                status=TicketStatus.NEW,
            )
            db.add(ticket)

            message = TicketMessage(
                id=uuid4(),
                ticket_id=ticket.id,
                role="customer",
                content="This is a test ticket body",
            )
            db.add(message)

            await db.commit()
            await db.refresh(ticket)
            print(f"Success! Created ticket: {ticket.id}")
        except Exception as e:
            await db.rollback()
            print(f"Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

asyncio.run(test_create_ticket())