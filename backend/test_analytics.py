"""Exact assertions for the analytics snapshot and the cost model.

Builds a synthetic dataset inside an isolated time window, so every expected
number is arithmetic rather than a guess, then removes it. Nothing is left
behind: a stray row here would corrupt the analytics it is testing.
"""

import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import delete

from app.core.llm import token_usage
from app.core.metrics import _snapshot
from app.core.pricing import estimate_cost_usd
from app.db.session import SyncSessionLocal
from app.models.base import (
    AgentFeedback,
    AuditLog,
    Intent,
    ProviderCall,
    Ticket,
    TicketMessage,
    TicketStatus,
)

# A window far in the past so the fixture cannot mix with real rows.
WINDOW_START = datetime(2001, 1, 1, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2001, 1, 1, 4, 0, tzinfo=timezone.utc)

CHECKS = 0
FAILURES: list[str] = []


def expect(label: str, actual, expected) -> None:
    global CHECKS
    CHECKS += 1
    if actual != expected:
        FAILURES.append(f"{label}\n    expected: {expected!r}\n    actual:   {actual!r}")


def test_cost_model() -> None:
    """The recorder's two pure inputs: token extraction and pricing."""

    class WithUsage:
        usage_metadata = {"input_tokens": 7, "output_tokens": 3}
        response_metadata = {}

    class MetadataOnly:
        usage_metadata = None
        response_metadata = {"token_usage": {"prompt_tokens": 11, "completion_tokens": 5}}

    class Silent:
        usage_metadata = None
        response_metadata = {}

    expect("tokens from usage_metadata", token_usage(WithUsage()), (7, 3))
    expect("tokens from response_metadata", token_usage(MetadataOnly()), (11, 5))
    expect("tokens absent report zero", token_usage(Silent()), (0, 0))

    # open-mistral-nemo is priced at $0.15 per 1M tokens in and out.
    expect(
        "cost for a priced model",
        estimate_cost_usd("open-mistral-nemo", 1000, 2000),
        (1000 * 0.15 + 2000 * 0.15) / 1_000_000,
    )
    expect("unpriced model returns None", estimate_cost_usd("no-such-model", 10, 10), None)


def build_fixture(db) -> list:
    """Four tickets across the window, three calls, audit entries and feedback."""
    ticket_ids: list = []
    call_ids: list = []

    def ticket(status: TicketStatus, offset_minutes: int, intent: Intent | None = None):
        row = Ticket(
            id=uuid4(),
            customer_id="cust_analytics_test",
            subject="analytics fixture",
            body="fixture",
            status=status,
            intent=intent,
            channel="chat",
            created_at=WINDOW_START + timedelta(minutes=offset_minutes),
        )
        db.add(row)
        ticket_ids.append(row.id)
        return row

    def message(ticket_id, role: str, offset_seconds: int) -> None:
        db.add(
            TicketMessage(
                id=uuid4(),
                ticket_id=ticket_id,
                role=role,
                content="fixture",
                created_at=WINDOW_START + timedelta(seconds=offset_seconds),
            )
        )

    def call(task: str, model: str, cost: str | None, latency: int, success: str = "true", error: str | None = None) -> None:
        row = ProviderCall(
            id=uuid4(),
            provider="mistral",
            model=model,
            task=task,
            input_tokens="100",
            output_tokens="20",
            latency_ms=str(latency),
            cost_estimate=cost,
            success=success,
            error=error,
            created_at=WINDOW_START + timedelta(minutes=1),
        )
        db.add(row)
        call_ids.append(row.id)

    def audit(ticket_id, action: str, payload=None) -> None:
        db.add(
            AuditLog(
                id=uuid4(),
                ticket_id=ticket_id,
                action=action,
                payload=payload,
                executed_by="test",
                created_at=WINDOW_START + timedelta(minutes=1),
            )
        )

    def feedback(ticket_id, original: str, edited: str) -> None:
        db.add(
            AgentFeedback(
                id=uuid4(),
                ticket_id=ticket_id,
                original_draft=original,
                edited_response=edited,
                agent_id="agent_test",
                created_at=WINDOW_START + timedelta(minutes=1),
            )
        )

    auto = ticket(TicketStatus.AUTO_RESOLVED, 10, Intent.REFUND)
    message(auto.id, "customer", 600)
    message(auto.id, "agent", 630)  # replied after 30s

    ticket(TicketStatus.DRAFT_FOR_REVIEW, 60)

    escalated = ticket(TicketStatus.ESCALATED, 120, Intent.GENERAL)
    audit(escalated.id, "escalated", {"reason": "below_routing_threshold"})

    resolved = ticket(TicketStatus.RESOLVED, 180)
    message(resolved.id, "customer", 10800)
    message(resolved.id, "agent", 10890)  # replied after 90s

    call("classifier", "open-mistral-nemo", "0.30", 1000)
    call("drafter", "open-mistral-nemo", "0.70", 3000, success="false", error="boom")
    call("classifier", "gpt-4o", None, 2000)  # no price on file

    audit(auto.id, "guardrail_violation", {"action": "refund", "requested": 4500})
    audit(auto.id, "refund_executed", {"refund_amount": 850})

    feedback(auto.id, "Same text", "Same text")  # approved unchanged
    feedback(auto.id, "Original", "Rewritten by the agent")  # edited
    feedback(auto.id, "Original", "")  # rejected

    db.commit()
    return ticket_ids + call_ids


def test_snapshot(db) -> None:
    snapshot = _snapshot(db, "24h", WINDOW_START, WINDOW_END)

    volume = snapshot["volume"]
    expect("volume.total", volume["total"], 4)
    expect("volume.auto_resolved", volume["auto_resolved"], 1)
    expect("volume.resolved", volume["resolved"], 1)
    expect("volume.draft_for_review", volume["draft_for_review"], 1)
    expect("volume.escalated", volume["escalated"], 1)
    expect("volume.new", volume["new"], 0)
    expect("volume.deflected", volume["deflected"], 2)
    expect("volume.deflection_rate", volume["deflection_rate"], 50.0)

    reply = snapshot["time_to_reply"]
    expect("time_to_reply.sample_size", reply["sample_size"], 2)
    expect("time_to_reply.average_seconds", reply["average_seconds"], 60.0)
    expect("time_to_reply.median_seconds", reply["median_seconds"], 60.0)
    expect("time_to_reply.p95_seconds", reply["p95_seconds"], 87.0)

    cost = snapshot["cost"]
    expect("cost.currency", cost["currency"], "USD")
    expect("cost.total_cost", cost["total_cost"], 1.0)
    expect("cost.cost_per_ticket", cost["cost_per_ticket"], 0.25)
    expect("cost.priced_calls", cost["priced_calls"], 2)
    expect("cost.unpriced_calls", cost["unpriced_calls"], 1)

    health = snapshot["provider_health"]
    expect("provider_health.calls", health["calls"], 3)
    expect("provider_health.failures", health["failures"], 1)
    expect("provider_health.error_rate", health["error_rate"], 33.33)
    expect("provider_health.average_latency_ms", health["average_latency_ms"], 2000.0)
    expect("provider_health.median_latency_ms", health["median_latency_ms"], 2000.0)
    expect("provider_health.p95_latency_ms", health["p95_latency_ms"], 2900.0)

    by_task = {entry["task"]: entry for entry in health["by_task"]}
    expect("by_task classifier calls", by_task["classifier"]["calls"], 2)
    expect("by_task classifier failures", by_task["classifier"]["failures"], 0)
    expect("by_task classifier cost", by_task["classifier"]["cost"], 0.30)
    expect("by_task drafter calls", by_task["drafter"]["calls"], 1)
    expect("by_task drafter failures", by_task["drafter"]["failures"], 1)
    expect("by_task drafter cost", by_task["drafter"]["cost"], 0.70)

    review = snapshot["draft_review"]
    expect("draft_review.total_reviewed", review["total_reviewed"], 3)
    expect("draft_review.approved_unchanged", review["approved_unchanged"], 1)
    expect("draft_review.edited", review["edited"], 1)
    expect("draft_review.rejected", review["rejected"], 1)
    expect("draft_review.acceptance_rate", review["acceptance_rate"], 33.3)

    escalation = snapshot["escalation_reasons"]
    expect("escalation_reasons.total_escalated", escalation["total_escalated"], 1)
    expect("escalation_reasons.reasons", escalation["reasons"], {"Below routing threshold": 1})

    guardrails = snapshot["guardrails"]
    expect("guardrails.refund_cap_interceptions", guardrails["refund_cap_interceptions"], 1)
    expect("guardrails.allow_listed_dispatches", guardrails["allow_listed_dispatches"], 1)
    expect("guardrails.format_deviations", guardrails["format_deviations"], 0)

    trend = snapshot["deflection_trend"]
    expect("trend bucket count", len(trend), 4)
    expect("trend labels", [bucket["label"] for bucket in trend], ["00:00", "01:00", "02:00", "03:00"])
    expect("trend deflected per bucket", [bucket["deflected"] for bucket in trend], [1, 0, 0, 1])
    expect("trend rates", [bucket["deflection_rate"] for bucket in trend], [100.0, 0.0, 0.0, 100.0])

    expect(
        "summary reports the deflection",
        snapshot["summary"].startswith("Deflected 2 of 4 tickets (50.0%)"),
        True,
    )
    expect("summary flags unpriced calls", "1 calls had no price on file" in snapshot["summary"], True)


def main() -> int:
    test_cost_model()

    with SyncSessionLocal() as db:
        created_ids = []
        try:
            created_ids = build_fixture(db)
            test_snapshot(db)
        finally:
            # ProviderCall has no foreign key; delete it explicitly. Tickets
            # cascade to messages, audit entries and feedback.
            db.execute(delete(ProviderCall).where(ProviderCall.id.in_(created_ids)))
            db.execute(delete(Ticket).where(Ticket.customer_id == "cust_analytics_test"))
            db.commit()

    if FAILURES:
        print(f"{len(FAILURES)} of {CHECKS} checks failed:\n")
        for failure in FAILURES:
            print(f"  {failure}")
        return 1

    print(f"{CHECKS}/{CHECKS} checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
