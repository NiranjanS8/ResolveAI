"""Provider registry and selection for chat and embedding models.

A provider is usable when settings hold a plausible (non-placeholder) API key
for it. This keeps the app runnable when only some providers are configured and
lets a deployment choose a preference order without code changes.
"""
from app.core.config import settings

CHAT_PROVIDERS = ("gemini", "mistral", "anthropic", "openai")
EMBEDDING_PROVIDERS = ("gemini", "mistral", "openai")

# Used when LLM_PROVIDER_ORDER is not set: the first provider with a configured
# key becomes the primary and the next one becomes its fallback.
DEFAULT_PROVIDER_ORDER = ("gemini", "mistral", "anthropic", "openai")

_PLACEHOLDER_MARKERS = ("your_", "here", "changeme", "xxx")


def looks_like_real_key(key: str | None) -> bool:
    if not key:
        return False
    lowered = key.lower()
    return len(key) > 20 and not any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def api_key_for(provider: str) -> str | None:
    return {
        "anthropic": settings.ANTHROPIC_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "mistral": settings.MISTRAL_API_KEY,
        "gemini": settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY,
    }.get(provider)


def is_configured(provider: str) -> bool:
    return looks_like_real_key(api_key_for(provider))


def provider_order() -> list[str]:
    """Preference order: an explicit ``LLM_PROVIDER_ORDER`` first, then any
    remaining known providers so configured keys are never ignored."""
    configured = settings.LLM_PROVIDER_ORDER
    order = [part.strip().lower() for part in configured.split(",") if part.strip()] if configured else []
    for provider in DEFAULT_PROVIDER_ORDER:
        if provider not in order:
            order.append(provider)
    return order


def select_provider(preferred: str | None, candidates: tuple[str, ...]) -> str | None:
    """Return the provider to use: the explicit preference when it is usable,
    otherwise the first configured provider in priority order."""
    if preferred and preferred in candidates and is_configured(preferred):
        return preferred
    for provider in provider_order():
        if provider in candidates and is_configured(provider):
            return provider
    return None
