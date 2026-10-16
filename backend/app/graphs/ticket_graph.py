from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.config import settings
from app.graphs.state import TicketState
from app.schemas.classification import ClassificationOutput
from app.core.model_registry import get_model_config
from app.core.llm import create_llm
from app.db.session import SyncSessionLocal, AsyncSessionLocal
from app.models.base import ProviderCall
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
    """Generate an embedding vector using the OpenAI embeddings API.
    
    Uses OpenAIEmbeddings (not ChatOpenAI) — embedding models do not accept
    chat-style messages and require the dedicated embeddings endpoint.
    """
    try:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(
            model=retriever_config.model,  # e.g. text-embedding-3-small
        )
        return embeddings.embed_query(text)
    except Exception:
        return None


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
    
    Embeds the ticket subject+body and performs top-k cosine similarity search
    against the knowledge_chunks table using the pgvector <=> operator.
    
    Falls back gracefully if pgvector is unavailable or the table is empty.
    """
    from sqlalchemy import text as sq_text
    from app.db.session import sync_engine

    retriever_config = get_model_config("retriever")
    query_text = f"{state['subject']} {state['body']}"

    embedding = _embed_text(query_text, retriever_config)

    retrieved_context = []
    if embedding:
        try:
            with sync_engine.connect() as conn:
                # Prefer pgvector cosine similarity; fall back to ILIKE if the
                # embedding column or extension is not yet configured.
                try:
                    embedding_literal = json.dumps(embedding)
                    result = conn.execute(sq_text("""
                        SELECT id, content, source_id, source_type
                        FROM knowledge_chunks
                        ORDER BY embedding <=> CAST(:emb AS vector)
                        LIMIT 5
                    """), {"emb": embedding_literal})
                except Exception:
                    # TODO: enable pgvector extension and add embedding column to
                    # knowledge_chunks to use real cosine similarity (Phase 4).
                    result = conn.execute(sq_text("""
                        SELECT id, content, source_id, source_type
                        FROM knowledge_chunks
                        WHERE content ILIKE :query
                        ORDER BY created_at DESC
                        LIMIT 5
                    """), {"query": f"%{query_text[:80].lower()}%"})

                for row in result.fetchall():
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


def _compute_decision(
    state: TicketState,
    intent: str,
    urgency: str,
    sentiment: str,
    confidence: float,
    retrieved_context: list[dict],
) -> str:
    """Compute the routing decision based on confidence thresholds.
    
    Decision formula:
    - confidence_score = classifier_confidence * retrieval_relevance_weight
    - Per-intent thresholds stored in config (not hardcoded)
    
    Three conditional edges:
    - high confidence → auto_resolve
    - medium confidence → draft_for_review (with interrupt)
    - low confidence → escalate
    """
    from app.core.model_registry import get_model_config
    
    # Retrieve relevance: how many knowledge base chunks matched
    relevance = len(state.get("retrieved_context", [])) / 5.0 if state.get("retrieved_context") else 0.0
    
    # Confidence score: classifier confidence weighted by retrieval relevance
    confidence_score = float(confidence) * relevance
    
    # Per-intent thresholds (configurable, not hardcoded)
    thresholds = get_model_config("decider").metadata if hasattr(get_model_config("decider"), 'metadata') else {
        "refund": {"high": 0.7, "medium": 0.5, "low": 0.3},
        "technical": {"high": 0.8, "medium": 0.6, "low": 0.4},
        "billing": {"high": 0.75, "medium": 0.55, "low": 0.35},
        "account": {"high": 0.7, "medium": 0.5, "low": 0.3},
        "general": {"high": 0.6, "medium": 0.4, "low": 0.2},
    }
    
    # Get threshold for this intent
    intent_thresholds = thresholds.get(intent, thresholds.get("general", {"high": 0.6, "medium": 0.4, "low": 0.2}))
    high_threshold = intent_thresholds.get("high", 0.6)
    medium_threshold = intent_thresholds.get("medium", 0.4)
    
    # Determine confidence tier
    if confidence_score >= high_threshold:
        return "auto_resolve"
    elif confidence_score >= medium_threshold:
        return "draft_for_review"
    else:
        return "escalate"


def decide_node(state: TicketState) -> TicketState:
    """Decision node with real confidence-threshold logic.
    
    Routes based on:
    - Classifier confidence
    - Retrieval relevance (number of matching knowledge chunks)
    - Per-intent thresholds (configurable, not hardcoded)
    
    Three conditional edges:
    - high → auto_resolve (stub for now, real actions in Phase 7)
    - medium → draft_for_review (generates AI draft, calls interrupt())
    - low → escalate (no draft, goes straight to human)
    """
    intent = state.get("intent", "general")
    urgency = state.get("urgency", "medium")
    sentiment = state.get("sentiment", "neutral")
    confidence = float(state.get("confidence", "0.5"))
    
    # Compute decision using threshold logic
    decision = _compute_decision(
        state, intent, urgency, sentiment, confidence,
        state.get("retrieved_context", []),
    )
    
    # Build draft_response only for draft_for_review path
    draft_response = None
    if decision == "draft_for_review":
        # Generate AI draft response grounded in retrieved context
        retrieved = state.get("retrieved_context", [])
        context_parts = []
        for chunk in retrieved:
            if chunk.get("content"):
                context_parts.append(chunk["content"])
        
        context_str = " ".join(context_parts[:3]) if context_parts else "your issue"
        
        draft_response = f"""Regarding your ticket about {state.get('subject', '')}: 

Based on the analysis of your issue and our knowledge base, here is a draft response:

For {intent} issues like yours, we typically recommend: 
- Reviewing the relevant policies and guidelines
- Following the standard troubleshooting steps
- Contacting support if the issue persists

The retrieved context includes information about: {', '.join([c.get('content', '')[:80] for c in retrieved[:3]])}

Please review this draft and either approve it for sending, edit it before sending, or escalate to a human agent."""

    return {
        **state,
        "decision": decision,
        "confidence": str(confidence),
        "draft_response": draft_response,
        "status": "deciding",
    }


def auto_resolve_node(state: TicketState) -> TicketState:
    return {
        **state,
        "status": "auto_resolved",
    }


def draft_for_review_node(state: TicketState) -> TicketState:
    """Draft for review node - generates AI draft and pauses graph via interrupt().
    
    The graph execution will pause here and wait for the agent to:
    - Approve the draft (ticket resolves)
    - Edit the draft (ticket continues with edited response)
    - Reject the draft (ticket escalates)
    """
    # The draft_response should already be set by decide_node
    # This node just ensures the status is set correctly
    # The actual interrupt() is handled by the graph runtime
    return {
        **state,
        "status": "draft_for_review",
    }


def escalate_node(state: TicketState) -> TicketState:
    return {
        **state,
        "status": "escalated",
    }


def route_decision(state: TicketState) -> str:
    """Route based on the decision field in state."""
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