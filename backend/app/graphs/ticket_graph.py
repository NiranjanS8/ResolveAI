from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import interrupt, Command
from app.core.audit import log_audit_action
from app.core.config import settings
from app.graphs.state import TicketState
from app.schemas.classification import ClassificationOutput, DraftOutput
from app.core.model_registry import get_model_config
from app.core.llm import invoke_structured_llm
from app.core.outbound import record_generated_deviation, send_customer_message
from app.core.promises import find_unverified_promises
from app.core.prompt_safety import (
    UNTRUSTED_DATA_GUARD,
    data_section,
    strip_hidden_content,
)
from app.core.text_format import sanitize_outbound


CLASSIFY_PROMPT = f"""You are a customer service ticket classifier. Analyze the ticket and classify it.

{UNTRUSTED_DATA_GUARD}

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


DRAFT_PROMPT_VERSION = "draft-plain-v2"

PLAIN_TEXT_RULES = """Write plain text only. No Markdown: no asterisks, underscores for emphasis, backticks, # headings, or table syntax. For lists use numbered lines like "1." or short separate sentences. Do not use emojis."""


DRAFT_PROMPT = f"""You are a customer support agent for an e-commerce company. Write the reply that will be sent to the customer.

{UNTRUSTED_DATA_GUARD}

Requirements:
- Be concise and friendly (at most about 150 words).
- Address the customer's actual request directly; acknowledge their tone.
- Rely only on the knowledge base excerpts provided. Never invent policies, prices, dates, or promises.
- Never say that an action has been taken or will be taken on the customer's account. You cannot issue refunds, cancel orders, reset passwords or change accounts, so do not promise any of them; describe what happens next and say a specialist will follow up.
- If the excerpts do not cover the request, say a specialist will follow up shortly instead of guessing.
- {PLAIN_TEXT_RULES}
- Sign off as "ResolveAI Support"."""


def _audit_untrusted_input(ticket_id, source: str, *values: str | None) -> None:
    """Record that invisible content was withheld from the model.

    Neutralising hidden text before the prompt would otherwise leave no trace:
    whoever hid it would have a silent path to the model. Only the kinds of
    content are recorded, never the text itself.
    """
    removed = sorted(
        {kind for value in values for kind in strip_hidden_content(value).removed}
    )
    if not removed:
        return
    log_audit_action(
        ticket_id,
        "untrusted_content_neutralized",
        {"source": source, "removed": removed},
        None,
        executed_by="ticket_graph.prompt_boundary",
    )


def _ticket_sections(state: TicketState) -> str:
    """The ticket's own words, fenced as data.

    Subject and body come straight from the customer, or from an inbound email,
    so neither is ever interpolated into an instruction: they arrive as data
    sections, with anything hidden inside them removed first.
    """
    return "\n\n".join(
        (
            data_section("ticket_subject", state.get("subject")),
            data_section("ticket_body", state.get("body")),
        )
    )


def build_classify_messages(state: TicketState) -> list[tuple[str, str]]:
    """The exact message pair sent to the classifier.

    Split out from the node so the boundary between instruction and data can be
    asserted without calling a model.
    """
    return [("system", CLASSIFY_PROMPT), ("human", _ticket_sections(state))]


def classify_node(state: TicketState) -> TicketState:
    config = get_model_config("classifier")

    _audit_untrusted_input(
        state.get("ticket_id"), "classify", state.get("subject"), state.get("body")
    )
    result = invoke_structured_llm(
        config, ClassificationOutput, build_classify_messages(state), "classifier"
    )

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
    stored chunks with pgvector's cosine-distance operator. The embedding
    column is an unconstrained ``vector`` because the embedding provider is
    switchable, so rows whose dimension differs from the query are ignored.

    A chunk promoted from an agent edit belongs to the customer whose ticket it
    came from; it is served only to that customer. Chunks that predate that rule
    carry no owner and are excluded too, because nothing approved them.
    """
    from sqlalchemy import text as sq_text
    from app.db.session import sync_engine
    from app.core.embeddings import embed_text

    query_text = f"{state['subject']} {state['body']}"
    embedding = embed_text(query_text)
    vector_literal = "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"

    retrieved_context = []
    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(
                sq_text("""
                    SELECT id, content, source_id, source_type, doc_title,
                           1 - (embedding <=> CAST(:query AS vector)) AS score
                    FROM knowledge_chunks
                    WHERE embedding IS NOT NULL
                      AND vector_dims(embedding) = :dimension
                      AND NOT (
                          source_type = 'feedback'
                          AND coalesce(meta->>'customer_id', '') <> :customer_id
                      )
                    ORDER BY embedding <=> CAST(:query AS vector)
                    LIMIT :limit
                """),
                {
                    "query": vector_literal,
                    "dimension": len(embedding),
                    "limit": settings.RETRIEVAL_TOP_K,
                    "customer_id": state.get("customer_id") or "",
                },
            ).fetchall()

        for row in rows:
            score = float(row[5]) if row[5] is not None else 0.0
            if score <= 0:
                continue
            retrieved_context.append({
                "id": str(row[0]),
                "content": row[1],
                "source_id": row[2],
                "source_type": row[3],
                "doc_title": row[4],
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


def _knowledge_text(state: TicketState) -> str:
    """The retrieved excerpts as plain text, limited to the ones sent to the model."""
    excerpts = [chunk.get("content", "") for chunk in (state.get("retrieved_context") or [])]
    present = [excerpt for excerpt in excerpts if excerpt and excerpt.strip()]
    return "\n\n".join(present[:3])


def _knowledge_section(state: TicketState) -> str:
    """The retrieved excerpts, fenced as data.

    Knowledge-base text is untrusted too: a document — or an agent edit promoted
    into the base — can carry a directive. It arrives as data, never as an
    instruction.
    """
    text = _knowledge_text(state)
    if not text:
        return "(no matching knowledge base article found)"
    return data_section("knowledge_base_excerpts", text)


def _draft_request(state: TicketState, intent: str) -> str:
    """The drafter's user turn: system metadata, then fenced data.

    The classification metadata sits outside the data sections because it is not
    customer writing: ``intent``, ``urgency`` and ``sentiment`` are constrained
    enums from ``ClassificationOutput``, so they carry no free text to smuggle.
    """
    return "\n\n".join(
        (
            "System-derived classification, for context only and not an instruction: "
            f"intent={intent}, urgency={state.get('urgency', 'medium')}, "
            f"sentiment={state.get('sentiment', 'neutral')}",
            data_section("ticket_subject", state.get("subject")),
            data_section("ticket_body", state.get("body")),
            _knowledge_section(state),
        )
    )


def build_draft_messages(state: TicketState, intent: str) -> list[tuple[str, str]]:
    """The exact message pair sent to the drafter, split out so it can be asserted."""
    return [("system", DRAFT_PROMPT), ("human", _draft_request(state, intent))]


def _generate_draft(state: TicketState, intent: str) -> str:
    """Draft a customer reply with the drafter model, grounded in retrieval.

    Structured output returns the body and nothing else, so the raw reply cannot
    arrive wrapped in commentary that we would have to strip.
    """
    config = get_model_config("drafter")

    _audit_untrusted_input(
        state.get("ticket_id"),
        "draft",
        state.get("subject"),
        state.get("body"),
        _knowledge_text(state),
    )

    result = invoke_structured_llm(
        config, DraftOutput, build_draft_messages(state, intent), "drafter"
    )
    return str(result.body).strip()


def _sanitize_draft(state: TicketState, draft: str) -> str:
    """Store the exact text that will be sent, counting any markup the model emitted.

    Sanitizing at generation time keeps the agent dashboard honest: the draft on
    screen is the plain text the customer receives. The send boundary sanitizes
    again, so a human pasting Markdown is still caught.
    """
    result = sanitize_outbound(draft)
    if result.changed:
        record_generated_deviation(
            state.get("ticket_id"),
            result.markers,
            source="ai_draft",
            prompt_version=DRAFT_PROMPT_VERSION,
        )
    return result.text


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
    - high → auto_resolve
    - medium → draft_for_review (generates AI draft, calls interrupt())
    - low → escalate (no draft, goes straight to human)

    A high score is necessary but not sufficient: a draft that promises an action
    only a human route can perform is downgraded to review, because the model
    writes those sentences confidently.
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
    
    # A reply is produced for both branches: draft_for_review sends it only once
    # a human approves, while auto_resolve sends it autonomously — and an
    # autonomous action must leave both a message and an audit entry behind.
    draft_response = None
    if decision in ("draft_for_review", "auto_resolve"):
        try:
            draft_response = _generate_draft(state, intent)
        except Exception:
            draft_response = _fallback_draft(state, intent)
        draft_response = _sanitize_draft(state, draft_response)

    relevance = max(
        (chunk.get("score", 0.0) for chunk in (state.get("retrieved_context") or [])),
        default=0.0,
    )
    routing_score = f"{confidence * relevance:.4f}"

    # Confidence decides how well the ticket matched, not what we are allowed to
    # promise. Nothing here or downstream can execute a refund, a cancellation or
    # a password reset on its own, so a reply that says one happened is false, and
    # it goes to a human instead of to the customer.
    if decision == "auto_resolve":
        promises = find_unverified_promises(draft_response)
        if promises:
            decision = "draft_for_review"
            log_audit_action(
                state.get("ticket_id"),
                "unverified_promise_blocked",
                {
                    "promises": promises,
                    "intent": intent,
                    "routing_score": routing_score,
                },
                state.get("confidence"),
                executed_by="ticket_graph.decide_node",
            )

    return {
        **state,
        "decision": decision,
        "confidence": str(confidence),
        "routing_score": routing_score,
        "draft_response": draft_response,
        "status": "draft_for_review" if decision == "draft_for_review" else "deciding",
    }


def auto_resolve_node(state: TicketState) -> TicketState:
    """Autonomous resolution — replies and is therefore audit-logged.

    The guardrail is that every autonomous action writes an audit_log entry, so
    this node records the decision inputs (intent, classifier certainty,
    retrieval relevance, final score) alongside the fact that a reply was sent.
    """
    confidence = state.get("confidence")
    relevance = max(
        (chunk.get("score", 0.0) for chunk in (state.get("retrieved_context") or [])),
        default=0.0,
    )
    reply = state.get("draft_response")
    if reply:
        send_customer_message(
            state.get("ticket_id"),
            reply,
            role="agent",
            source="auto_resolve",
            prompt_version=DRAFT_PROMPT_VERSION,
        )

    log_audit_action(
        state.get("ticket_id"),
        "auto_resolved",
        {
            "intent": state.get("intent"),
            "classifier_confidence": confidence,
            "retrieval_relevance": round(relevance, 4),
            "routing_score": state.get("routing_score"),
            "reply_sent": bool(reply),
        },
        confidence,
        executed_by="ticket_graph.auto_resolve_node",
    )
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
    """Escalation branch, audit-logged with its reason.

    Recording *why* a ticket left automation is what makes the escalation
    breakdown real; without it the only recoverable signal is the final status.
    """
    log_audit_action(
        state.get("ticket_id"),
        "escalated",
        {
            "reason": "below_routing_threshold",
            "intent": state.get("intent"),
            "routing_score": state.get("routing_score"),
        },
        state.get("confidence"),
        executed_by="ticket_graph.escalate_node",
    )
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