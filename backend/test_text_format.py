"""Plain-text formatting tests for outbound customer messages.

Covers three layers:

1. Unit: exact sanitizer output for the markup we actually see from models.
2. Email path: ten realistic drafts through ``prepare_outbound('email', ...)``,
   asserting the ``text/plain`` part is free of Markdown residue and that the
   ``text/html`` part is escaped.
3. Send boundary: a real round trip through ``send_customer_message`` proving the
   stored message and the deviation counter match what was rendered.

Run from the backend directory (needs the database up for layer 3):

    python test_text_format.py

Exits non-zero if any check fails.
"""
import sys
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.outbound import prepare_outbound, send_customer_message
from app.core.text_format import plain_text_to_html, sanitize_outbound, to_plain_text
from app.db.session import SyncSessionLocal
from app.graphs.ticket_graph import DRAFT_PROMPT_VERSION
from app.models.base import AuditLog, ProviderCall, Ticket, TicketMessage

# Exact sanitizer output. Each entry is (markdown_input, expected_plain_text).
UNIT_CASES: list[tuple[str, str]] = [
    ("**Refund** issued", "Refund issued"),
    ("__Refund__ issued", "Refund issued"),
    ("*Refund* issued", "Refund issued"),
    ("- item\n- item", "- item\n- item"),
    ("* item\n* item", "- item\n- item"),
    ("1. first\n2. second", "1. first\n2. second"),
    ("# Title", "Title"),
    ("## Refund policy", "Refund policy"),
    ("[link](https://x.com)", "link (https://x.com)"),
    ("<https://x.com>", "https://x.com"),
    ("order_id_123", "order_id_123"),
    ("5 * 3", "5 * 3"),
    ("2 * 3", "2 * 3"),
    ("Use `inline` code", "Use inline code"),
    ("```\ncode line\n```", "code line"),
    ("| a | b |\n| --- | --- |\n| 1 | 2 |", "a | b\n1 | 2"),
    ("~~struck~~ text", "struck text"),
    ("**bold** and order_id_77 and 4 * 5", "bold and order_id_77 and 4 * 5"),
    ("Line one\n\n\n\nLine two", "Line one\n\nLine two"),
    ("Trailing space   ", "Trailing space"),
]

# Ten drafts in the shape a model produces for this product's tickets.
SAMPLE_DRAFTS: list[str] = [
    "**Refund** issued\n\nYour refund of ₹500 is on its way.\n\n- Check your bank\n- Wait 3-5 days",
    "## Order status\n\nOrder #12345 has shipped.\n\n1. Track it here\n2. Reply if it does not arrive",
    "Your *subscription* has been cancelled. No further charges will apply.",
    "You can reset your password at [our help centre](https://resolveai.example/reset).",
    "Your login uses the token `order_id_123`. Keep it private.",
    "Here is the reference:\n\n```\nREFUND-8837\n```\n\nQuote it in any reply.",
    "| Item | Status |\n| --- | --- |\n| Refund | Processed |\n| Email | Sent |",
    "**Heads up** about order #9981: your refund is processing.",
    "* Charge reversed\n* Balance updated\n\nWe are sorry for the trouble.",
    "Quick check: is that 2 * 3 or a typo? Your ticket id is order_id_5510.",
]

MARKDOWN_RESIDUE = (
    ("** bold", r"\*\*"),
    ("__ bold", r"__"),
    ("backtick", r"`"),
    ("link", r"\]\("),
    ("~~ strike", r"~~"),
    # A lone asterisk is legitimate maths ("2 * 3"); only an asterisk touching a
    # word is a leftover emphasis marker.
    ("emphasis", r"\*(?![\s*])|(?<![\s*])\*"),
    ("heading", r"(?m)^#{1,6}(?:\s|$)"),
)


def check(label: str, condition: bool, detail: str = "") -> bool:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" - {detail}" if detail else ""))
    return condition


def residue(text: str) -> list[str]:
    """Markdown patterns that must not survive into a customer-facing body."""
    return [label for label, pattern in MARKDOWN_RESIDUE if re.search(pattern, text)]


def check_unit_cases() -> list[bool]:
    print("Unit: exact sanitizer output")
    results = []
    for markdown, expected in UNIT_CASES:
        actual = to_plain_text(markdown)
        results.append(check(repr(markdown), actual == expected, f"-> {actual!r}"))

    results.append(check("None becomes empty string", to_plain_text(None) == ""))
    results.append(check("plain text passes through unchanged", to_plain_text("All good, thanks.") == "All good, thanks."))
    results.append(check("clean text is not reported as changed", sanitize_outbound("All good.").changed is False))
    results.append(check("markup is reported with its kind", "strong" in sanitize_outbound("**a**").markers))
    return results


def check_html_rendering() -> list[bool]:
    print()
    print("Unit: email HTML part")
    rendered = plain_text_to_html("Hi <b>Sam</b> & co.\n\nSee https://x.com/a?b=1&c=2. Done.")
    return [
        check("model markup is escaped, not rendered", "&lt;b&gt;" in rendered and "<b>" not in rendered),
        check("ampersands are escaped", "&amp;" in rendered),
        check("paragraphs are wrapped", rendered.count("<p>") == 2, rendered),
        check("line breaks are preserved", "<br>" in plain_text_to_html("one\ntwo")),
        check(
            "bare URLs are auto-linked inside the escaped text",
            '<a href="https://x.com/a?b=1&amp;c=2">https://x.com/a?b=1&amp;c=2</a>' in rendered,
            rendered,
        ),
        check("sentence punctuation stays outside the link", "</a>." in rendered),
        check("script tags cannot survive", "<script" not in plain_text_to_html("<script>alert(1)</script>")),
    ]


def check_email_path() -> list[bool]:
    print()
    print(f"Integration: {len(SAMPLE_DRAFTS)} drafts through the email path")
    results = []
    for index, draft in enumerate(SAMPLE_DRAFTS, start=1):
        envelope = prepare_outbound("email", draft)
        problems = residue(envelope.plain_text)
        results.append(check(f"draft {index}: text/plain is clean", not problems, f"residue={problems}"))
        results.append(
            check(
                f"draft {index}: text/html is escaped and wrapped",
                envelope.html_body is not None
                and envelope.html_body.startswith("<p>")
                and "<script" not in envelope.html_body,
            )
        )

    chat = prepare_outbound("chat", SAMPLE_DRAFTS[0])
    results.append(check("chat has no HTML part", chat.html_body is None))
    results.append(check("chat keeps newlines for pre-wrap", "\n" in chat.plain_text))

    # Guard against a residue scan that grows so lenient it proves nothing.
    results.append(
        check("residue scan catches unstripped markup", len(residue("**b** `c` [l](u)\n# H")) >= 4, str(residue("**b** `c` [l](u)\n# H")))
    )
    results.append(check("residue scan allows maths and order ids", residue("2 * 3 for order #12345") == []))

    survivors = [to_plain_text(draft) for draft in SAMPLE_DRAFTS]
    results.append(check("snake_case survives all drafts", all("order_id_" in text for text in survivors[4:5] + survivors[9:])))
    results.append(check("math expression survives", "2 * 3" in survivors[9]))

    try:
        prepare_outbound("carrier-pigeon", "hi")
        results.append(check("unknown channel is rejected", False))
    except ValueError:
        results.append(check("unknown channel is rejected", True))
    return results


def check_send_boundary() -> list[bool]:
    print()
    print("Integration: send boundary round trip (database)")
    results = []
    ticket_id = None
    marker = f"test-format-{uuid4().hex[:8]}"

    with SyncSessionLocal() as db:
        ticket = Ticket(
            id=uuid4(),
            customer_id=marker,
            subject="Boundary test",
            body="Markdown in, plain text out.",
            channel="email",
        )
        db.add(ticket)
        db.commit()
        ticket_id = ticket.id
        before = db.query(ProviderCall).filter(ProviderCall.task == "format_sanitize").count()

    try:
        sent = send_customer_message(
            ticket_id,
            SAMPLE_DRAFTS[0],
            role="agent",
            source="test",
            prompt_version=DRAFT_PROMPT_VERSION,
        )
        results.append(check("boundary returns a clean text/plain part", not residue(sent.envelope.plain_text)))

        with SyncSessionLocal() as db:
            message = db.get(TicketMessage, sent.message_id)
            results.append(check("stored content equals the text/plain part", message.content == sent.envelope.plain_text))
            results.append(check("stored content carries no markup", not residue(message.content)))
            results.append(check("email message stores its HTML part", (message.meta or {}).get("html_body", "").startswith("<p>")))
            results.append(check("deviation is flagged on the message", (message.meta or {}).get("sanitized") is True))

            audits = (
                db.query(AuditLog)
                .filter(AuditLog.ticket_id == ticket_id, AuditLog.action == "format_sanitized")
                .all()
            )
            results.append(check("one deviation audit entry", len(audits) == 1, f"{len(audits)} found"))
            if audits:
                results.append(check("audit names the markup kinds", "strong" in (audits[0].payload or {}).get("markers", [])))
                results.append(check("audit records the prompt version", (audits[0].payload or {}).get("prompt_version") == DRAFT_PROMPT_VERSION))

            after = db.query(ProviderCall).filter(ProviderCall.task == "format_sanitize").count()
            results.append(check("counter increments by one", after == before + 1, f"{before} -> {after}"))

        # The graph passes the ticket id as a string; the boundary must accept both.
        send_customer_message(str(ticket_id), "Thanks for your patience.", role="agent", source="test")
        with SyncSessionLocal() as db:
            audits = (
                db.query(AuditLog)
                .filter(AuditLog.ticket_id == ticket_id, AuditLog.action == "format_sanitized")
                .all()
            )
            after_clean = db.query(ProviderCall).filter(ProviderCall.task == "format_sanitize").count()
            results.append(check("clean text writes no deviation", len(audits) == 1 and after_clean == before + 1))
    finally:
        with SyncSessionLocal() as db:
            # Only the counter rows this test could have written. The column is
            # timestamptz, so the cutoff must be timezone-aware.
            cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
            db.query(ProviderCall).filter(
                ProviderCall.task == "format_sanitize",
                ProviderCall.created_at >= cutoff,
            ).delete(synchronize_session=False)
            ticket = db.get(Ticket, ticket_id)
            if ticket is not None:
                db.delete(ticket)
            db.commit()
    return results


def main() -> int:
    results = []
    results += check_unit_cases()
    results += check_html_rendering()
    results += check_email_path()
    results += check_send_boundary()

    print()
    passed = sum(1 for result in results if result)
    print(f"{passed}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
