"""Seed the queue with realistic support tickets.

Development data. It removes the ad-hoc rows left by earlier manual test runs
(identifiable by their customer-id prefixes) and replays a curated set of
realistic conversations through the real graph, so every status, draft and
audit entry is genuine rather than hand-written.

Usage:
    python seed_tickets.py
    python seed_tickets.py --reset
    python seed_tickets.py --prune-only
"""

from __future__ import annotations

import argparse
from uuid import uuid4

from sqlalchemy import delete, select

from app.db.session import SyncSessionLocal
from app.graphs.runner import apply_graph_result, run_ticket_graph
from app.models.base import Ticket, TicketMessage, TicketStatus

# Customer ids used by manual/e2e testing. Anything created by them is noise in
# a demo queue.
TEST_CUSTOMER_PREFIXES = ("cust_e2e", "cust_kb_", "cust_hitl", "cust_test", "cust_123")

SEED_TICKETS: list[tuple[str, str, str, str]] = [
    (
        "cust_priya_88",
        "chat",
        "Damaged item in order #BLR-4421",
        "One of the items in my order arrived damaged. I would like a refund of ₹850 back to my UPI account.",
    ),
    (
        "cust_amit_corp",
        "email",
        "Invoiced for licenses we never activated",
        "We were billed ₹3,200 for extra cloud licenses that were never activated. Please issue a credit refund.",
    ),
    (
        "cust_sneha_k",
        "email",
        "Consignment #MUM-7729 has not arrived",
        "Could you check the courier status for consignment #MUM-7729? It was due yesterday.",
    ),
    (
        "cust_vikram_s",
        "email",
        "Locked out after resetting two-factor authentication",
        "I reset 2FA on my Android device and now I cannot get into my dashboard. I need access restored.",
    ),
    (
        "cust_deepa_r",
        "chat",
        "Charged twice for the same order",
        "My card was charged twice for order #BLR-9931. Please reverse the duplicate charge.",
    ),
    (
        "cust_ravi_n",
        "chat",
        "Cannot change the email on my account",
        "I need to move my account to a new email address but the settings page will not save the change.",
    ),
    (
        "cust_karan_v",
        "chat",
        "Please cancel order #DEL-2210",
        "I would like to cancel order #DEL-2210 before it ships, please.",
    ),
    (
        "cust_nisha_b",
        "email",
        "App crashes when I upload a receipt",
        "The app closes every time I try to attach a receipt to a claim. This has happened six times today.",
    ),
    (
        "cust_meera_j",
        "chat",
        "Where is my October invoice?",
        "I cannot find the invoice for my October subscription payment. Could you resend it?",
    ),
    (
        "cust_arjun_t",
        "chat",
        "Hello",
        "Hi, are you there?",
    ),
]


def prune_test_tickets(db) -> int:
    """Delete every ticket created by a known test customer id."""
    condition = None
    for prefix in TEST_CUSTOMER_PREFIXES:
        clause = Ticket.customer_id.like(f"{prefix}%")
        condition = clause if condition is None else condition | clause
    removed = db.execute(delete(Ticket).where(condition)).rowcount or 0
    db.commit()
    return removed


def prune_seed_tickets(db) -> int:
    """Delete the seed tickets so they can be replayed through the current graph."""
    customer_ids = [customer_id for customer_id, *_ in SEED_TICKETS]
    removed = db.execute(delete(Ticket).where(Ticket.customer_id.in_(customer_ids))).rowcount or 0
    db.commit()
    return removed


def seed(db, seeds: list[tuple[str, str, str, str]]) -> tuple[int, int]:
    """Create each seed ticket and run it through the real pipeline."""
    created = skipped = 0
    for customer_id, channel, subject, body in seeds:
        existing = db.execute(
            select(Ticket.id).where(Ticket.customer_id == customer_id, Ticket.subject == subject)
        ).first()
        if existing:
            skipped += 1
            continue

        ticket = Ticket(
            id=uuid4(),
            customer_id=customer_id,
            subject=subject,
            body=body,
            status=TicketStatus.NEW,
            channel=channel,
        )
        db.add(ticket)
        db.add(TicketMessage(id=uuid4(), ticket_id=ticket.id, role="customer", content=body))
        db.commit()
        db.refresh(ticket)

        try:
            result = run_ticket_graph(ticket)
            apply_graph_result(ticket, result)
            db.commit()
            print(f"  + {subject!r} -> {ticket.status.value} ({ticket.intent})")
        except Exception as exc:  # keep seeding the rest
            db.rollback()
            print(f"  ! {subject!r} failed: {exc}")
        created += 1
    return created, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed realistic demo tickets.")
    parser.add_argument("--prune-only", action="store_true", help="remove test rows and stop")
    parser.add_argument(
        "--reset", action="store_true", help="also delete the seed tickets and replay them"
    )
    args = parser.parse_args()

    with SyncSessionLocal() as db:
        print(f"Pruned {prune_test_tickets(db)} test ticket(s).")
        if args.prune_only:
            return
        if args.reset:
            print(f"Removed {prune_seed_tickets(db)} seed ticket(s) for replay.")
        created, skipped = seed(db, SEED_TICKETS)
        print(f"Seeded {created} ticket(s), skipped {skipped} already present.")


if __name__ == "__main__":
    main()
