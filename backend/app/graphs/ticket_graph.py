from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.config import settings
from app.graphs.state import TicketState


def classify_node(state: TicketState) -> TicketState:
    return {
        **state,
        "intent": "general",
        "urgency": "medium",
        "sentiment": "neutral",
        "status": "classifying",
    }


def retrieve_node(state: TicketState) -> TicketState:
    return {
        **state,
        "retrieved_context": [],
        "status": "retrieving",
    }


def decide_node(state: TicketState) -> TicketState:
    return {
        **state,
        "decision": "escalate",
        "confidence": "0.1",
        "status": "deciding",
    }


def auto_resolve_node(state: TicketState) -> TicketState:
    return {
        **state,
        "status": "auto_resolved",
    }


def draft_for_review_node(state: TicketState) -> TicketState:
    return {
        **state,
        "draft_response": "This is a draft response for review.",
        "status": "draft_for_review",
    }


def escalate_node(state: TicketState) -> TicketState:
    return {
        **state,
        "status": "escalated",
    }


def route_decision(state: TicketState) -> str:
    decision = state.get("decision", "escalate")
    if decision == "auto_resolve":
        return "auto_resolve"
    elif decision == "draft_for_review":
        return "draft_for_review"
    else:
        return "escalate"


def build_graph() -> StateGraph:
    workflow = StateGraph(TicketState)

    workflow.add_node("classify", classify_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("auto_resolve", auto_resolve_node)
    workflow.add_node("draft_for_review", draft_for_review_node)
    workflow.add_node("escalate", escalate_node)

    workflow.set_entry_point("classify")
    workflow.add_edge("classify", "retrieve")
    workflow.add_edge("retrieve", "decide")
    workflow.add_conditional_edges(
        "decide",
        route_decision,
        {
            "auto_resolve": "auto_resolve",
            "draft_for_review": "draft_for_review",
            "escalate": "escalate",
        },
    )
    workflow.add_edge("auto_resolve", END)
    workflow.add_edge("draft_for_review", END)
    workflow.add_edge("escalate", END)

    return workflow


_checkpointer = None
_checkpointer_cm = None

def get_compiled_graph():
    global _checkpointer, _checkpointer_cm
    graph = build_graph()
    if _checkpointer is None:
        _checkpointer_cm = PostgresSaver.from_conn_string(settings.DATABASE_URL.replace("+psycopg", ""))
        _checkpointer = _checkpointer_cm.__enter__()
        _checkpointer.setup()
    return graph.compile(checkpointer=_checkpointer)