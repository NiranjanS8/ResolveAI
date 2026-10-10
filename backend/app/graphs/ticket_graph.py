from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.config import settings
from app.graphs.state import TicketState
from app.schemas.classification import ClassificationOutput
from app.core.model_registry import get_model_config
from app.core.llm import create_llm
from app.db.session import SyncSessionLocal
from uuid import uuid4
import time


CLASSIFY_PROMPT = """You are a customer service ticket classifier. Analyze the ticket and classify it.

Ticket:
Subject: {subject}
Body: {body}

Classify the ticket into exactly one of these categories:
- general: General inquiries, greetings, unclear requests
- billing: Billing questions, payment issues, invoice inquiries
- technical: Technical problems, bugs, feature not working
- account: Account management, profile changes, login issues
- refund: Refund requests, returns, money back
- order_status: Order tracking, shipping, delivery questions
- password_reset: Password reset, forgot password, login help
- cancellation: Subscription/service cancellation requests

Also determine:
- urgency: low, medium, high, critical
- sentiment: negative, neutral, positive
- confidence: 0.0 to 1.0

Return structured output with reasoning."""


def classify_node(state: TicketState) -> TicketState:
    primary_config = get_model_config("classifier")
    fallback_config = primary_config.fallback
    
    primary_llm = create_llm(primary_config).with_structured_output(ClassificationOutput).with_fallbacks(
        [create_llm(fallback_config).with_structured_output(ClassificationOutput)],
        exception_type=Exception,
    )
    
    messages = [
        ("system", CLASSIFY_PROMPT),
        ("human", f"Subject: {state['subject']}\nBody: {state['body']}"),
    ]
    
    import time
    start = time.perf_counter()
    result = primary_llm.invoke(messages)
    latency_ms = int((time.perf_counter() - start) * 1000)
    
    # Log the call (primary or fallback) to provider_calls table
    with SyncSessionLocal() as db:
        call = ProviderCall(
            id=uuid4(),
            provider=primary_config.provider,
            model=primary_config.model,
            task="classifier",
            latency_ms=str(latency_ms),
            success="true",
        )
        db.add(call)
        db.commit()
    
    return {
        **state,
        "intent": result.intent,
        "urgency": result.urgency,
        "sentiment": result.sentiment,
        "confidence": str(result.confidence),
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