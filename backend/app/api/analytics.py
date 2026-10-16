from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.base import AgentFeedback, ProviderCall, Ticket, TicketStatus

router = APIRouter(prefix="/analytics", tags=["analytics"])

RANGE_DELTAS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


@router.get("")
async def get_analytics(
    range: str = Query("30d", pattern="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
):
    """Compute dashboard metrics directly from the database."""
    since = datetime.now(timezone.utc) - RANGE_DELTAS[range]

    status_rows = await db.execute(
        select(Ticket.status, func.count())
        .where(Ticket.created_at >= since)
        .group_by(Ticket.status)
    )
    status_counts = {
        (status.value if hasattr(status, "value") else str(status)): count
        for status, count in status_rows.all()
    }
    total = sum(status_counts.values())
    auto_resolved = status_counts.get("auto_resolved", 0)
    resolved = status_counts.get("resolved", 0)
    draft_for_review = status_counts.get("draft_for_review", 0)
    escalated = status_counts.get("escalated", 0)
    deflected = auto_resolved + resolved
    deflection = round(deflected / total * 100, 2) if total else 0.0

    cost_row = await db.execute(
        select(func.coalesce(func.sum(cast(ProviderCall.cost_estimate, Float)), 0.0))
        .where(ProviderCall.created_at >= since)
    )
    total_cost = float(cost_row.scalar() or 0.0)
    cost_per_ticket = round(total_cost / total, 4) if total else 0.0

    handle_row = await db.execute(
        select(func.avg(func.extract("epoch", Ticket.updated_at - Ticket.created_at)))
        .where(Ticket.created_at >= since)
        .where(Ticket.status.in_([TicketStatus.AUTO_RESOLVED, TicketStatus.RESOLVED]))
    )
    avg_seconds_raw = handle_row.scalar()
    avg_seconds = int(avg_seconds_raw) if avg_seconds_raw else 0

    feedback_row = await db.execute(
        select(func.count()).select_from(AgentFeedback).where(AgentFeedback.created_at >= since)
    )
    total_feedback = feedback_row.scalar() or 0
    csat_score = round(deflected / total * 100, 1) if total else 0.0

    escalation_rows = await db.execute(
        select(Ticket.intent, func.count())
        .where(Ticket.status == TicketStatus.ESCALATED)
        .where(Ticket.created_at >= since)
        .group_by(Ticket.intent)
    )
    escalation_breakdown: dict[str, int] = {}
    for intent, count in escalation_rows.all():
        key = intent.value if hasattr(intent, "value") else (str(intent) if intent else "unclassified")
        escalation_breakdown[key] = count

    executive_summary = (
        f"ResolveAI auto-resolved {deflected} of {total} tickets "
        f"({deflection}% deflection) in the last {range}, at an estimated "
        f"provider cost of {total_cost:.2f}."
    )

    return {
        "deflection_rate": {
            "deflection_rate": deflection,
            "total_tickets": total,
            "auto_resolved": auto_resolved,
            "draft_for_review": draft_for_review,
            "escalated": escalated,
        },
        "cost_per_ticket": {
            "cost_per_ticket": cost_per_ticket,
            "total_cost": round(total_cost, 2),
            "currency": "INR",
        },
        "average_handle_time": {
            "average_handle_time_seconds": avg_seconds,
            "formatted": f"{avg_seconds}s",
        },
        "csat_proxy": {
            "csat_score": csat_score,
            "positive_count": deflected,
            "total_feedback": total_feedback,
        },
        "escalation_breakdown": escalation_breakdown,
        "executive_summary": executive_summary,
    }
