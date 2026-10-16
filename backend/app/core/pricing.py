"""Provider price table for real cost accounting.

Prices are USD per 1,000,000 tokens as (input, output) and are a *snapshot* of
each provider's published list price. Provider pricing changes, so treat this
table as data to be kept current, not as a constant to be trusted. Verify
against the provider's pricing page when a number looks wrong.

A model that is absent here is deliberately reported as *unpriced* (``None``)
rather than costing zero, so a missing price shows up as "no cost data" instead
of a measured ``$0.00``.
"""

from __future__ import annotations

PRICE_SNAPSHOT_DATE = "2026-10"

# USD per 1M tokens: (input, output)
MODEL_PRICES: dict[str, tuple[float, float]] = {
    # Mistral
    "open-mistral-nemo": (0.15, 0.15),
    "mistral-small-latest": (0.20, 0.60),
    "mistral-large-latest": (2.00, 6.00),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # Anthropic
    "claude-3-haiku-20240307": (0.25, 1.25),
    "claude-3-sonnet-20240229": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    # Google
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
}


def is_priced(model: str) -> bool:
    return model in MODEL_PRICES


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """USD cost of one call, or ``None`` when the model has no price on file."""
    price = MODEL_PRICES.get(model)
    if price is None:
        return None
    input_price, output_price = price
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
