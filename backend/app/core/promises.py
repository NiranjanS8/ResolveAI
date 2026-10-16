"""Commitments an autonomous reply must not make.

An agent can only do what code lets it do: refunds, cancellations and password
resets run when a human calls the action routes, and the refund cap is enforced
there. A drafting model does not know any of that, so it happily writes "I will
process a full refund for the duplicate charge immediately" and an auto-resolved
reply sends that sentence to the customer. No money moves, but the customer has
been told it did.

:func:`find_unverified_promises` finds those sentences so the decision node can
hand the ticket to a human instead of sending them. The list is deliberately
aimed at *consequential account actions* rather than at process or courtesy
language, and it is conservative on purpose: every hit costs an automatic
resolution, so a false positive is a review, and a false negative is a false
promise on a customer's screen.

Only the matching labels are ever returned, never the sentence, because the
sentence is customer-facing model text and does not belong in an audit payload.
"""

from __future__ import annotations

import re

# A refund is the action with a code-enforced cap and the one the drafter reaches
# for most often. "Your refund" alone is included: even a policy-shaped sentence
# like "your refund will be processed within five days" tells the customer we
# started something we did not.
_REFUND = (
    r"\byour refund\b",
    r"\brefund\b[^.!?\n]{0,40}\b(?:has been|have been|is being|will be|was)\b"
    r"[^.!?\n]{0,20}\b(?:processed|approved|issued|initiated|completed|credited|sent)\b",
    r"\brefund\b[^.!?\n]{0,30}\b(?:processed|approved|issued|initiated|completed|credited)\b",
    r"\b(?:process|processed|processing|issue|issued|issuing|approve|approved|approving|"
    r"initiate|initiated|initiating|complete|completed|completing|credit|credited|crediting|"
    r"reimburse|reimbursed|reimbursing)\b[^.!?\n]{0,30}\brefund\b",
)

_CANCELLATION = (
    r"\bcancel(?:led|ed|ling|ing|s)?\b[^.!?\n]{0,30}\b(?:your|the)\b"
    r"[^.!?\n]{0,20}\b(?:order|subscription|account|plan|booking)\b",
)

_PASSWORD_RESET = (
    r"\bpassword\b[^.!?\n]{0,25}\b(?:has been|have been|is|will be|was)\b"
    r"[^.!?\n]{0,15}\breset\b",
    r"\breset\b[^.!?\n]{0,25}\b(?:your|the)\b[^.!?\n]{0,15}\bpassword\b",
    r"\b(?:password\s+)?reset link\b[^.!?\n]{0,25}\b(?:sent|emailed|on its way|dispatched)\b",
)

_ACCOUNT = (
    r"\b(?:close[ds]?|closing|delete[ds]?|deleting)\b[^.!?\n]{0,25}\b(?:your|the)\b"
    r"[^.!?\n]{0,15}\baccount\b",
)

_COMPENSATION = (
    r"\bcredit(?:ed)?\b[^.!?\n]{0,25}\b(?:your|to your|the)\b[^.!?\n]{0,15}\baccount\b",
    r"\bcompensat(?:e|ed|ing|ion)\b",
    r"\bwaive[ds]?\b[^.!?\n]{0,25}\b(?:fee|charge|charges|shipping|late)\b",
    r"\bguarantee(?:d|e|s)?\b[^.!?\n]{0,25}\b(?:refund|delivery|arrival|resolution|fix)\b",
)

_ESCALATION = (
    r"\b(?:i|we)(?:'ll| will|'ve| have)\b[^.!?\n]{0,40}\bescalat(?:e|ed|ing)\b",
    r"\bexpedite[ds]?\b[^.!?\n]{0,25}\b(?:order|shipment|delivery|refund|replacement)\b",
)

# First-person past tense over an action verb: a claim that something already
# happened, written by a model that cannot make it happen.
_COMPLETED_ACTION = (
    r"\b(?:i|we)(?:'ve| have)\b[^.!?\n]{0,20}\b(?:refunded|approved|processed|issued|"
    r"reset|cancelled|canceled|closed|credited|escalated|expedited|reimbursed|"
    r"compensated|waived)\b",
)

_UNVERIFIED_PROMISES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("refund", _REFUND),
    ("cancellation", _CANCELLATION),
    ("password_reset", _PASSWORD_RESET),
    ("account", _ACCOUNT),
    ("compensation", _COMPENSATION),
    ("escalation", _ESCALATION),
    ("completed_action", _COMPLETED_ACTION),
)

_COMPILED = tuple(
    (label, tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns))
    for label, patterns in _UNVERIFIED_PROMISES
)

# Model output uses typographic apostrophes ("I’ll") as often as ASCII ones, and a
# commitment the patterns cannot see is a commitment the guard cannot block.
_APOSTROPHES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u02bc": "'", "\u00b4": "'"})


def find_unverified_promises(text: str | None) -> list[str]:
    """The kinds of unperformed action the text commits us to, in a stable order."""
    if not text:
        return []
    normalized = text.translate(_APOSTROPHES)
    return [
        label
        for label, patterns in _COMPILED
        if any(pattern.search(normalized) for pattern in patterns)
    ]
