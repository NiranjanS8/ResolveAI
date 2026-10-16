"""Smoke test for the compiled ticket graph.

Creates a real ticket, runs the graph through it and removes the ticket
afterwards, because the nodes write messages and audit rows against a ticket id
that has to exist (``audit_log.ticket_id`` is a foreign key).

Makes real provider calls, so it needs the worker's provider key configured:

    python test_graph.py
"""
import asyncio
import sys
from uuid import uuid4

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.db.session import SyncSessionLocal
from app.graphs.runner import run_ticket_graph
from app.models.base import Ticket


def test_graph():
    with SyncSessionLocal() as db:
        ticket = Ticket(
            id=uuid4(),
            customer_id="cust_graph_smoke_test",
            subject="Where is my order?",
            body="It was supposed to arrive last Tuesday.",
            channel="chat",
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        print(f"Running graph for ticket {ticket.id}...")
        try:
            result = run_ticket_graph(ticket)
        finally:
            db.delete(ticket)
            db.commit()

    print(f"Result: {result}")
    assert result.get("ticket_id") == str(ticket.id)
    assert result.get("intent"), "the classifier returned no intent"
    assert result.get("decision") in {"auto_resolve", "draft_for_review", "escalate"}
    print("Graph smoke test passed.")
    return result


if __name__ == "__main__":
    test_graph()
