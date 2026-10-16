"""The single send boundary for customer-facing messages.

Every outbound message — autonomous replies, approved drafts, agent edits and
agent-typed messages — goes through :func:`send_customer_message`. It sanitizes
first, so no code path can deliver Markdown to a customer, and it records any
deviation from the plain-text contract so we can see how often a model or a
human breaks the format.

The sanitizer runs in one place on purpose: a channel cannot opt out of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.core.audit import log_audit_action
from app.core.text_format import plain_text_to_html, sanitize_outbound
from app.db.session import SyncSessionLocal
from app.models.base import ProviderCall, Ticket, TicketMessage

CHANNEL_EMAIL = "email"
CHANNEL_CHAT = "chat"
CHANNELS = {CHANNEL_EMAIL, CHANNEL_CHAT}

# A customer's own words are stored verbatim; every other role is outbound.
INBOUND_ROLES = {"customer"}

# Deviations are counted per prompt version, so a prompt that ignores the
# plain-text rules shows up in the data instead of only in a customer's inbox.
INTERNAL_PROVIDER = "internal"
FORMAT_TASK = "format_sanitize"


@dataclass(frozen=True)
class OutboundEnvelope:
    """A sanitized message rendered for one channel.

    ``plain_text`` is exactly what the customer sees: the email ``text/plain``
    part, or the chat body. ``html_body`` is set only for email and is generated
    here from the already-sanitized text, never from raw model output.
    """

    channel: str
    plain_text: str
    html_body: str | None
    markers: list[str]


@dataclass(frozen=True)
class SendResult:
    message_id: UUID
    envelope: OutboundEnvelope


def prepare_outbound(channel: str, body: str | None) -> OutboundEnvelope:
    """Sanitize ``body`` and render it for ``channel`` (pure, no database)."""
    if channel not in CHANNELS:
        raise ValueError(f"Unsupported channel: {channel!r}")

    result = sanitize_outbound(body)
    html_body = plain_text_to_html(result.text) if channel == CHANNEL_EMAIL else None
    return OutboundEnvelope(
        channel=channel,
        plain_text=result.text,
        html_body=html_body,
        markers=result.markers if result.changed else [],
    )


def send_customer_message(
    ticket_id: UUID | str,
    body: str | None,
    *,
    role: str = "agent",
    source: str = "agent_message",
    prompt_version: str | None = None,
    agent_id: str | None = None,
) -> SendResult:
    """Sanitize, log and persist one outbound message.

    The channel is read from the ticket so a caller cannot render for the wrong
    one. Returns the stored message id and the rendered envelope.
    """
    if isinstance(ticket_id, str):
        ticket_id = UUID(ticket_id)

    with SyncSessionLocal() as db:
        ticket = db.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError(f"Ticket not found: {ticket_id}")

        envelope = prepare_outbound(ticket.channel, body)
        if envelope.markers:
            _record_format_deviation(
                db,
                ticket_id=ticket.id,
                source=source,
                channel=envelope.channel,
                markers=envelope.markers,
                prompt_version=prompt_version,
                agent_id=agent_id,
            )

        message = TicketMessage(
            id=uuid4(),
            ticket_id=ticket.id,
            role=role,
            content=envelope.plain_text,
            meta={
                "channel": envelope.channel,
                "format": "plain_text",
                "sanitized": bool(envelope.markers),
                "source": source,
                "prompt_version": prompt_version,
                "html_body": envelope.html_body,
            },
        )
        db.add(message)
        db.commit()
        return SendResult(message_id=message.id, envelope=envelope)


def record_generated_deviation(
    ticket_id: UUID | str,
    markers: list[str],
    *,
    source: str,
    prompt_version: str | None = None,
) -> None:
    """Count markup a model emitted at generation time.

    Drafts are sanitized when they are generated so the agent dashboard shows the
    exact text that will be sent. This records that first pass; the send boundary
    records anything a human adds afterwards. Since a draft is cleaned before it
    is ever sent, a violation is counted once rather than once per pass.
    """
    if not markers:
        return
    with SyncSessionLocal() as db:
        _record_format_deviation(
            db,
            ticket_id=ticket_id,
            source=source,
            channel=None,
            markers=markers,
            prompt_version=prompt_version,
            agent_id=None,
        )


def _record_format_deviation(
    db,
    *,
    ticket_id: UUID | str,
    source: str,
    channel: str | None,
    markers: list[str],
    prompt_version: str | None,
    agent_id: str | None,
) -> None:
    """Write the deviation to the audit trail and the aggregate counter."""
    log_audit_action(
        ticket_id,
        "format_sanitized",
        {
            "source": source,
            "channel": channel,
            "markers": markers,
            "prompt_version": prompt_version,
        },
        executed_by=agent_id or "outbound_send_boundary",
    )

    # For internal formatter events the prompt version is carried in ``model``
    # and the count is aggregated by ``task``, alongside real provider calls.
    db.add(
        ProviderCall(
            id=uuid4(),
            provider=INTERNAL_PROVIDER,
            model=prompt_version or "n/a",
            task=FORMAT_TASK,
            input_tokens="0",
            output_tokens="0",
            latency_ms="0",
            cost_estimate="0",
            success="true",
        )
    )
    db.commit()
