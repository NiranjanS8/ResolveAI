"""Running the ticket graph, for both the HTTP layer and the queue worker.

Ticket processing calls the LLM, so the API no longer runs it inside the request
that creates the ticket — it enqueues a job and the worker drains it. Both sides
have to start, resume and record the graph the same way, so that logic lives here
rather than in either caller.
"""
from __future__ import annotations

from langgraph.types import Command

from app.graphs import get_compiled_graph
from app.graphs.state import TicketState
from app.models.base import Ticket, TicketStatus


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
        "routing_score": None,
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
