"""Analytics computed from stored rows.

One implementation serves both the HTTP endpoint (``app/api/analytics.py``) and
the CLI report (``analytics_dashboard.py``), so the numbers on screen and on the
console cannot diverge.

Every figure is derived from the database. Where the data cannot support a
metric it is reported as absent (``None``) or paired with an explicit count of
what was excluded, rather than shown as a fabricated or silently-zero value.
Costs are USD, the currency providers bill in.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Float, cast, func, select
from sqlalchemy.orm import Session

from app.core.outbound import INBOUND_ROLES, INTERNAL_PROVIDER
from app.db.session import SyncSessionLocal
from app.models.base import AgentFeedback, AuditLog, ProviderCall, Ticket, TicketMessage, TicketStatus

RANGE_DELTAS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}
DEFAULT_RANGE = "30d"

DEFLECTED_STATUSES = (TicketStatus.AUTO_RESOLVED, TicketStatus.RESOLVED)

# Actions that mark a ticket as having left automation, mapped to the reason
# shown in the breakdown. The graph writes ``escalated``; the API writes
# ``draft_rejected`` when an agent discards a draft.
ESCALATION_ACTIONS = ("escalated", "draft_rejected")
ESCALATION_REASON_LABELS = {
    "below_routing_threshold": "Below routing threshold",
    "agent_rejected_draft": "Agent rejected draft",
}

# Allow-listed side-effect actions, counted from the audit trail.
ALLOW_LISTED_ACTIONS = ("refund_executed", "order_status_checked", "password_reset_executed")

_DAILY = ("7d", "30d")


def analytics_snapshot(range_id: str = DEFAULT_RANGE) -> dict:
    """Snapshot of every metric for ``range_id`` (``24h``/``7d``/``30d``)."""
    delta = RANGE_DELTAS.get(range_id, RANGE_DELTAS[DEFAULT_RANGE])
    until = datetime.now(timezone.utc)
    since = until - delta
    with SyncSessionLocal() as db:
        return _snapshot(db, range_id, since, until)


def _snapshot(db: Session, range_id: str, since: datetime, until: datetime) -> dict:
    window = {"range": range_id, "since": since.isoformat(), "until": until.isoformat()}

    status_counts = _status_counts(db, since, until)
    total = sum(status_counts.values())
    deflected = sum(status_counts.get(_value(status), 0) for status in DEFLECTED_STATUSES)

    volume = _volume(status_counts, total, deflected)
    cost = _cost(db, since, until, total)

    return {
        "window": window,
        "summary": _summary(volume, cost, range_id),
        "volume": volume,
        "time_to_reply": _time_to_reply(db, since, until),
        "cost": cost,
        "provider_health": _provider_health(db, since, until),
        "draft_review": _draft_review(db, since, until),
        "escalation_reasons": _escalation_reasons(db, since, until, status_counts),
        "guardrails": _guardrails(db, since, until),
        "deflection_trend": _deflection_trend(db, range_id, since, until),
    }


# ── Individual metrics ─────────────────────────────────────────────────────

def _status_counts(db: Session, since: datetime, until: datetime) -> dict[str, int]:
    rows = db.execute(
        select(Ticket.status, func.count())
        .where(Ticket.created_at >= since, Ticket.created_at < until)
        .group_by(Ticket.status)
    ).all()
    return {_value(status): count for status, count in rows}


def _volume(status_counts: dict[str, int], total: int, deflected: int) -> dict:
    return {
        "total": total,
        "auto_resolved": status_counts.get("auto_resolved", 0),
        "resolved": status_counts.get("resolved", 0),
        "draft_for_review": status_counts.get("draft_for_review", 0),
        "escalated": status_counts.get("escalated", 0),
        "new": status_counts.get("new", 0),
        "deflected": deflected,
        "deflection_rate": round(deflected / total * 100, 2) if total else None,
    }


def _time_to_reply(db: Session, since: datetime, until: datetime) -> dict:
    """Seconds from ticket creation to the first outbound reply.

    Measured from the customer's message to the first message we sent back, so
    it is a fixed fact about the conversation rather than ``updated_at``, which
    any later write would move.
    """
    first_reply = (
        select(
            TicketMessage.ticket_id.label("ticket_id"),
            func.min(TicketMessage.created_at).label("first_reply_at"),
        )
        .where(TicketMessage.role.notin_(tuple(INBOUND_ROLES)))
        .group_by(TicketMessage.ticket_id)
        .subquery()
    )
    rows = db.execute(
        select(func.extract("epoch", first_reply.c.first_reply_at - Ticket.created_at))
        .select_from(Ticket)
        .join(first_reply, first_reply.c.ticket_id == Ticket.id)
        .where(Ticket.created_at >= since, Ticket.created_at < until)
    ).scalars().all()

    durations = sorted(float(seconds) for seconds in rows if seconds is not None and seconds >= 0)
    if not durations:
        return {"sample_size": 0, "average_seconds": None, "median_seconds": None, "p95_seconds": None}

    return {
        "sample_size": len(durations),
        "average_seconds": round(sum(durations) / len(durations), 2),
        "median_seconds": round(_percentile(durations, 0.50), 2),
        "p95_seconds": round(_percentile(durations, 0.95), 2),
    }


def _cost(db: Session, since: datetime, until: datetime, total_tickets: int) -> dict:
    real_calls = _real_calls(since, until)
    calls, priced_calls, total_cost = db.execute(
        select(
            func.count(),
            func.count(ProviderCall.cost_estimate),
            func.coalesce(func.sum(cast(ProviderCall.cost_estimate, Float)), 0.0),
        ).where(*real_calls)
    ).one()
    total_cost = float(total_cost or 0.0)

    return {
        "currency": "USD",
        "total_cost": round(total_cost, 6),
        "cost_per_ticket": round(total_cost / total_tickets, 6) if total_tickets else None,
        "priced_calls": priced_calls,
        "unpriced_calls": calls - priced_calls,
    }


def _provider_health(db: Session, since: datetime, until: datetime) -> dict:
    """Call volume, failures and latency percentiles per task.

    Latency and failures are read from the same rows the cost comes from, so a
    provider that is slow or failing is visible instead of inferred.
    """
    real_calls = _real_calls(since, until)
    calls, failures = db.execute(
        select(
            func.count(),
            func.count().filter(ProviderCall.success != "true"),
        ).where(*real_calls)
    ).one()

    latency = db.execute(
        select(
            func.avg(cast(ProviderCall.latency_ms, Float)),
            func.percentile_cont(0.50).within_group(cast(ProviderCall.latency_ms, Float)),
            func.percentile_cont(0.95).within_group(cast(ProviderCall.latency_ms, Float)),
        ).where(*real_calls)
    ).one()

    by_task = [
        {
            "task": task,
            "calls": task_calls,
            "failures": task_failures,
            "cost": round(float(cost or 0.0), 6),
            "average_latency_ms": round(float(avg_latency), 1) if avg_latency is not None else None,
        }
        for task, task_calls, task_failures, cost, avg_latency in db.execute(
            select(
                ProviderCall.task,
                func.count(),
                func.count().filter(ProviderCall.success != "true"),
                func.coalesce(func.sum(cast(ProviderCall.cost_estimate, Float)), 0.0),
                func.avg(cast(ProviderCall.latency_ms, Float)),
            )
            .where(*real_calls)
            .group_by(ProviderCall.task)
            .order_by(func.count().desc())
        ).all()
    ]

    return {
        "calls": calls,
        "failures": failures,
        "error_rate": round(failures / calls * 100, 2) if calls else None,
        "average_latency_ms": round(float(latency[0]), 1) if latency[0] is not None else None,
        "median_latency_ms": round(float(latency[1]), 1) if latency[1] is not None else None,
        "p95_latency_ms": round(float(latency[2]), 1) if latency[2] is not None else None,
        "by_task": by_task,
    }


def _draft_review(db: Session, since: datetime, until: datetime) -> dict:
    """How agents treated the model's drafts: approved as-is, edited, or binned.

    This replaces the old "CSAT proxy", which was the deflection rate relabelled
    and never read the feedback table. It is named for what it measures.
    """
    rows = db.execute(
        select(AgentFeedback.original_draft, AgentFeedback.edited_response)
        .where(AgentFeedback.created_at >= since, AgentFeedback.created_at < until)
    ).all()

    approved = sum(1 for original, edited in rows if edited and edited.strip() == (original or "").strip())
    rejected = sum(1 for _, edited in rows if not edited or not edited.strip())
    total = len(rows)

    return {
        "total_reviewed": total,
        "approved_unchanged": approved,
        "edited": total - approved - rejected,
        "rejected": rejected,
        "acceptance_rate": round(approved / total * 100, 1) if total else None,
    }


def _escalation_reasons(db: Session, since: datetime, until: datetime, status_counts: dict[str, int]) -> dict:
    rows = db.execute(
        select(AuditLog.ticket_id, AuditLog.action, AuditLog.payload)
        .join(Ticket, Ticket.id == AuditLog.ticket_id)
        .where(Ticket.created_at >= since, Ticket.created_at < until)
        .where(Ticket.status == TicketStatus.ESCALATED)
        .where(AuditLog.action.in_(ESCALATION_ACTIONS))
    ).all()

    reasons: dict[str, int] = {}
    reasoned_tickets: set = set()
    for ticket_id, action, payload in rows:
        if ticket_id in reasoned_tickets:
            continue
        reasoned_tickets.add(ticket_id)
        key = (payload or {}).get("reason") if action == "escalated" else "agent_rejected_draft"
        label = ESCALATION_REASON_LABELS.get(key, ESCALATION_REASON_LABELS["below_routing_threshold"])
        reasons[label] = reasons.get(label, 0) + 1

    unclassified = status_counts.get("escalated", 0) - len(reasoned_tickets)
    if unclassified > 0:
        reasons["Not recorded"] = unclassified

    return {"total_escalated": status_counts.get("escalated", 0), "reasons": reasons}


def _guardrails(db: Session, since: datetime, until: datetime) -> dict:
    """Policy enforcement counts, all read from the audit trail."""

    def count(action: str) -> int:
        return db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == action, AuditLog.created_at >= since, AuditLog.created_at < until)
        ).scalar() or 0

    return {
        "refund_cap_interceptions": count("guardrail_violation"),
        "allow_listed_dispatches": sum(count(action) for action in ALLOW_LISTED_ACTIONS),
        "format_deviations": count("format_sanitized"),
    }


def _deflection_trend(db: Session, range_id: str, since: datetime, until: datetime) -> list[dict]:
    """Tickets created and deflected per bucket, from real rows."""
    trunc_unit = "day" if range_id in _DAILY else "hour"
    # Truncate in UTC explicitly so bucket labels do not shift with the database
    # session's timezone setting.
    bucket = func.date_trunc(trunc_unit, func.timezone("UTC", Ticket.created_at))

    rows = db.execute(
        select(
            bucket.label("bucket"),
            func.count(),
            func.count().filter(Ticket.status.in_(DEFLECTED_STATUSES)),
        )
        .where(Ticket.created_at >= since, Ticket.created_at < until)
        .group_by(bucket)
        .order_by(bucket)
    ).all()

    counts = {_as_utc(created): (total, deflected) for created, total, deflected in rows}

    series = []
    for boundary in _bucket_boundaries(since, until, trunc_unit):
        total, deflected = counts.get(boundary, (0, 0))
        series.append({
            "label": boundary.strftime("%H:00" if trunc_unit == "hour" else "%b %d"),
            "total": total,
            "deflected": deflected,
            "deflection_rate": round(deflected / total * 100, 2) if total else None,
        })
    return series


# ── Helpers ────────────────────────────────────────────────────────────────

def _summary(volume: dict, cost: dict, range_id: str) -> str:
    """One honest sentence: what was deflected, and what it cost."""
    window = {"24h": "last 24 hours", "7d": "last 7 days", "30d": "last 30 days"}.get(
        range_id, "selected window"
    )
    total = volume["total"]
    if total == 0:
        return f"No tickets were created in the {window}."

    sentence = (
        f"Deflected {volume['deflected']} of {total} tickets "
        f"({volume['deflection_rate']}%) in the {window}."
    )
    if cost["priced_calls"]:
        sentence += (
            f" Provider spend was ${cost['total_cost']:.4f} "
            f"(${cost['cost_per_ticket']:.6f} per ticket) across {cost['priced_calls']} priced calls."
        )
    if cost["unpriced_calls"]:
        sentence += f" {cost['unpriced_calls']} calls had no price on file and are excluded from cost."
    return sentence


def _real_calls(since: datetime, until: datetime):
    """Filter clause excluding the internal formatter counter rows."""
    return (
        ProviderCall.provider != INTERNAL_PROVIDER,
        ProviderCall.created_at >= since,
        ProviderCall.created_at < until,
    )


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    position = fraction * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _bucket_boundaries(since: datetime, until: datetime, trunc_unit: str) -> list[datetime]:
    step = timedelta(hours=1) if trunc_unit == "hour" else timedelta(days=1)
    if trunc_unit == "hour":
        cursor = since.replace(minute=0, second=0, microsecond=0)
    else:
        cursor = since.replace(hour=0, minute=0, second=0, microsecond=0)
    boundaries = []
    while cursor < until:
        boundaries.append(cursor)
        cursor += step
    return boundaries


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
