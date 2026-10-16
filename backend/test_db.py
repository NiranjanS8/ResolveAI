"""Round-trip smoke test for ticket and message persistence.

Cleans up after itself: a test row left in the database would inflate the
analytics that read these tables.
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from uuid import uuid4

from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.models.base import Ticket, TicketMessage, TicketStatus


async def test_create_ticket() -> None:
    ticket_id = uuid4()
    async with AsyncSessionLocal() as db:
        try:
            db.add(
                Ticket(
                    id=ticket_id,
                    customer_id="cust_test_db",
                    subject="Test ticket",
                    body="This is a test ticket body",
                    status=TicketStatus.NEW,
                )
            )
            db.add(
                TicketMessage(
                    id=uuid4(),
                    ticket_id=ticket_id,
                    role="customer",
                    content="This is a test ticket body",
                )
            )
            await db.commit()

            stored = await db.get(Ticket, ticket_id)
            assert stored is not None, "ticket was not persisted"
            print(f"Success! Created ticket: {stored.id}")
        except Exception as exc:
            await db.rollback()
            print(f"Error: {type(exc).__name__}: {exc}")
            import traceback

            traceback.print_exc()
            raise
        finally:
            # Cascade removes the message with the ticket.
            await db.execute(delete(Ticket).where(Ticket.id == ticket_id))
            await db.commit()


asyncio.run(test_create_ticket())
