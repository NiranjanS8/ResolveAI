"""Confidence-threshold configuration for the decision engine.

Routing thresholds are a tunable, so they live here rather than being buried in
the graph node. ``high`` is the auto-resolve cutoff and ``medium`` the
draft-for-review cutoff; anything below ``medium`` escalates.
"""

DEFAULT_THRESHOLDS = {"high": 0.6, "medium": 0.4}

DECISION_THRESHOLDS: dict[str, dict[str, float]] = {
    "refund": {"high": 0.7, "medium": 0.5},
    "technical": {"high": 0.8, "medium": 0.6},
    "billing": {"high": 0.75, "medium": 0.55},
    "account": {"high": 0.7, "medium": 0.5},
    "order_status": {"high": 0.65, "medium": 0.45},
    "password_reset": {"high": 0.65, "medium": 0.45},
    "cancellation": {"high": 0.7, "medium": 0.5},
    "general": DEFAULT_THRESHOLDS,
}


def thresholds_for(intent: str) -> dict[str, float]:
    """Return the routing thresholds for an intent, falling back to defaults."""
    return DECISION_THRESHOLDS.get(intent, DEFAULT_THRESHOLDS)
