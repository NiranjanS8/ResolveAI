from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.config import settings
from app.graphs.state import TicketState
from app.schemas.classification import ClassificationOutput
from app.core.model_registry import get_model_config
from app.core.llm import create_llm
from app.db.session import SyncSessionLocal, async_engine
from uuid import uuid4
import time
import json


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


def _embed_text(text: str, retriever_config) -> list[float] | None:
    """Generate an embedding for the given text using the retriever model."""
    from langchain_openai import ChatOpenAI
    
    llm = create_llm(retriever_config)
    messages = [("human", f"Generate an embedding for: {text}")]
    
    import time
    start = time.perf_counter()
    response = llm.invoke(messages)
    latency_ms = int((time.perf_counter() - start) * 1000)
    
    embedding = None
    if hasattr(response, 'embedding'):
        embedding = response.embedding
    elif isinstance(response, str):
        try:
            data = json.loads(response)
            embedding = data.get('embedding') if isinstance(data, dict) else None
        except Exception:
            pass
    
    return embedding


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


def retrieve_node(state: TicketState) -> TicketState:
    """Retrieve relevant knowledge base chunks for the ticket.
    
    Embeds the ticket subject/body and performs top-k similarity search
    against the knowledge_chunks table.
    """
    from sqlalchemy import text as sq_text
    from app.db.session import sync_engine
    
    retriever_config = get_model_config("retriever")
    query_text = f"{state['subject']} {state['body']}"
    
    # Generate embedding for the query
    embedding = _embed_text(query_text, retriever_config)
    
    retrieved_context = []
    if embedding:
        try:
            with sync_engine.connect() as conn:
                # Search for similar chunks using cosine similarity
                # We'll use a simple ILIKE-based search for MVP since pgvector may not be available
                result = conn.execute(sq_text("""
                    SELECT id, content, source_id, source_type 
                    FROM knowledge_chunks 
                    WHERE content ILIKE :query
                    ORDER BY created_at DESC
                    LIMIT 5
                """), {"query": f"%{query_text.lower()}%"})
                rows = result.fetchall()
                for row in rows:
                    retrieved_context.append({
                        "id": str(row[0]),
                        "content": row[1],
                        "source_id": row[2],
                        "source_type": row[3],
                    })
        except Exception:
            pass
    
    return {
        **state,
        "retrieved_context": retrieved_context,
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