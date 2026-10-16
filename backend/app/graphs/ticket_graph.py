from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import interrupt, Command
from app.core.config import settings
from app.graphs.state import TicketState
from app.schemas.classification import ClassificationOutput
from app.core.model_registry import get_model_config
from app.core.llm import create_llm
from app.db.session import SyncSessionLocal, AsyncSessionLocal
from app.models.base import ProviderCall
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
- confidence: how certain you are about the intent category
- reasoning: brief explanation

Report confidence honestly. It decides whether a customer reply is sent automatically or routed to a human, so an inflated number causes mistakes:
- 0.90-1.00: the request clearly matches exactly one category, leaving no doubt.
- 0.70-0.89: it matches one category but with slight ambiguity.
- 0.40-0.69: the request is vague, very short, or could fit several categories.
- 0.00-0.39: you cannot tell what the customer needs. Use "general" for these.
Do not default to a high number: vague or underspecified tickets must score below 0.70."""


DRAFT_PROMPT = """You are a customer support agent for an e-commerce company. Write the reply that will be sent to the customer.

Requirements:
- Be concise and friendly (at most about 150 words).
- Address the customer's actual request directly; acknowledge their tone.
- Rely only on the knowledge base excerpts provided. Never invent policies, prices, dates, or promises.
- If the excerpts do not cover the request, say a specialist will follow up shortly instead of guessing.
- Sign off as "ResolveAI Support"."""


def classify_node(state: TicketState) -> TicketState:
    primary_config = get_model_config("classifier")
    fallback_config = primary_config.fallback
    
    primary_llm = create_llm(primary_config).with_structured_output(ClassificationOutput)
    if fallback_config:
        primary_llm = primary_llm.with_fallbacks(
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
    """Retrieve the most relevant knowledge-base chunks for the ticket.

    Embeds the ticket subject+body with the shared embedding function and ranks
    stored chunks by cosine similarity. Embeddings are stored as a plain
    ``FLOAT[]`` column, so similarity is computed in Python (fine at MVP scale).
    """
    from sqlalchemy import text as sq_text
    from app.db.session import sync_engine
    from app.core.embeddings import embed_text, cosine_similarity

    query_text = f"{state['subject']} {state['body']}"
    embedding = embed_text(query_text)

    retrieved_context = []
    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(sq_text("""
                SELECT id, content, source_id, source_type, embedding
                FROM knowledge_chunks
            """)).fetchall()

        scored = []
        for row in rows:
            chunk_embedding = list(row[4]) if row[4] else []
            score = cosine_similarity(embedding, chunk_embedding)
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)

        for score, row in scored[:5]:
            if score <= 0:
                continue
            retrieved_context.append({
                "id": str(row[0]),
                "content": row[1],
                "source_id": row[2],
                "source_type": row[3],
                "score": round(score, 4),
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
    from app.core.thresholds import thresholds_for

    # Retrieval relevance: how well the best knowledge-base chunk matches. A
    # count-based ratio is always ~1.0 for dense embeddings and carries no
    # signal, so the top similarity score is what actually gates confidence.
    relevance = max((chunk.get("score", 0.0) for chunk in retrieved_context), default=0.0)

    # Confidence score: classifier confidence weighted by retrieval relevance
    confidence_score = float(confidence) * relevance
    
    # Per-intent thresholds (configurable, not hardcoded)
    intent_thresholds = thresholds_for(intent)
    high_threshold = intent_thresholds["high"]
    medium_threshold = intent_thresholds["medium"]
    
    # Determine confidence tier
    if confidence_score >= high_threshold:
        return "auto_resolve"
    elif confidence_score >= medium_threshold:
        return "draft_for_review"
    else:
        return "escalate"


def _knowledge_excerpts(state: TicketState) -> str:
    """Format the retrieved knowledge-base chunks for the drafter prompt."""
    excerpts = [chunk.get("content", "") for chunk in state.get("retrieved_context", [])]
    excerpts = [excerpt for excerpt in excerpts if excerpt]
    if not excerpts:
        return "(no matching knowledge base article found)"
    return "\n".join(f"- {excerpt}" for excerpt in excerpts[:3])


def _generate_draft(state: TicketState, intent: str) -> str:
    """Draft a customer reply with the drafter model, grounded in retrieval."""
    config = get_model_config("drafter")
    llm = create_llm(config)
    if config.fallback:
        llm = llm.with_fallbacks([create_llm(config.fallback)], exception_type=Exception)

    request = (
        f"Subject: {state.get('subject', '')}\n"
        f"Body: {state.get('body', '')}\n"
        f"Detected intent: {intent}; urgency: {state.get('urgency', 'medium')}; "
        f"sentiment: {state.get('sentiment', 'neutral')}\n\n"
        f"Knowledge base excerpts:\n{_knowledge_excerpts(state)}"
    )

    start = time.perf_counter()
    reply = llm.invoke([("system", DRAFT_PROMPT), ("human", request)])
    latency_ms = int((time.perf_counter() - start) * 1000)

    with SyncSessionLocal() as db:
        db.add(ProviderCall(
            id=uuid4(),
            provider=config.provider,
            model=config.model,
            task="drafter",
            latency_ms=str(latency_ms),
            success="true",
        ))
        db.commit()

    content = reply.content
    if isinstance(content, list):
        content = " ".join(str(part) for part in content)
    return str(content).strip()


def _fallback_draft(state: TicketState, intent: str) -> str:
    """Deterministic draft used when the drafter model is unavailable."""
    return (
        f"Thanks for contacting us about \"{state.get('subject', '')}\". "
        f"We're looking into your {intent} request and a specialist will follow up shortly. "
        "— ResolveAI Support"
    )


def decide_node(state: TicketState) -> TicketState:
    """Decision node with real confidence-threshold logic.
    
    Routes based on:
    - Classifier confidence
    - Retrieval relevance (top knowledge-chunk similarity)
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
        try:
            draft_response = _generate_draft(state, intent)
        except Exception:
            draft_response = _fallback_draft(state, intent)

    return {
        **state,
        "decision": decision,
        "confidence": str(confidence),
        "draft_response": draft_response,
        "status": "draft_for_review" if decision == "draft_for_review" else "deciding",
    }


def auto_resolve_node(state: TicketState) -> TicketState:
    return {
        **state,
        "status": "auto_resolved",
    }


def draft_for_review_node(state: TicketState) -> TicketState:
    """Pause the graph for human review via interrupt().

    Execution stops here and the run waits in a "waiting" state (persisted by
    the checkpointer) until the agent resumes it with a decision:
    - "approve": send the AI draft as-is; ticket resolves.
    - "edit": send the agent's edited_response; ticket resolves.
    - "reject": discard the draft; ticket escalates to a human.
    """
    review = interrupt({
        "type": "draft_review",
        "ticket_id": state.get("ticket_id"),
        "intent": state.get("intent"),
        "urgency": state.get("urgency"),
        "draft_response": state.get("draft_response"),
    })

    review = review or {}
    action = review.get("action", "reject")

    if action == "approve":
        return {**state, "status": "resolved", "decision": "approved"}
    if action == "edit":
        return {
            **state,
            "status": "resolved",
            "decision": "edited",
            "draft_response": review.get("edited_response") or state.get("draft_response"),
        }
    return {**state, "status": "escalated", "decision": "rejected"}


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