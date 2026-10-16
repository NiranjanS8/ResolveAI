from typing import Any, Dict
from pydantic import BaseModel

from app.core.providers import is_configured, provider_order


class ModelConfig(BaseModel):
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1000
    fallback: "ModelConfig | None" = None


# Per-provider chat models for each task: (model, temperature, max_tokens).
# Cheap models handle classification and decisions; the stronger model drafts.
PROVIDER_MODELS: Dict[str, Dict[str, tuple[str, float, int]]] = {
    "gemini": {
        "classifier": ("gemini-2.5-flash", 0.0, 500),
        "decider": ("gemini-2.5-flash", 0.0, 500),
        "drafter": ("gemini-2.5-pro", 0.3, 1000),
    },
    "mistral": {
        "classifier": ("mistral-small-latest", 0.0, 500),
        "decider": ("mistral-small-latest", 0.0, 500),
        "drafter": ("mistral-large-latest", 0.3, 1000),
    },
    "anthropic": {
        "classifier": ("claude-3-haiku-20240307", 0.0, 500),
        "decider": ("claude-3-haiku-20240307", 0.0, 500),
        "drafter": ("claude-3-sonnet-20240229", 0.3, 1000),
    },
    "openai": {
        "classifier": ("gpt-4o-mini", 0.0, 500),
        "decider": ("gpt-4o-mini", 0.0, 500),
        "drafter": ("gpt-4o", 0.3, 1000),
    },
}

# Used when no provider has a configured key; the request then fails with a
# clear "no API key" error instead of a missing-config error.
DEFAULT_PROVIDER = "anthropic"


def _config_for(provider: str, task: str) -> ModelConfig:
    model, temperature, max_tokens = PROVIDER_MODELS[provider][task]
    return ModelConfig(provider=provider, model=model, temperature=temperature, max_tokens=max_tokens)


def _resolve_providers() -> tuple[str, str | None]:
    configured = [p for p in provider_order() if p in PROVIDER_MODELS and is_configured(p)]
    if configured:
        return configured[0], (configured[1] if len(configured) > 1 else None)
    return DEFAULT_PROVIDER, None


def _build_registry() -> Dict[str, ModelConfig]:
    primary, fallback = _resolve_providers()
    registry: Dict[str, ModelConfig] = {}
    for task in PROVIDER_MODELS[primary]:
        config = _config_for(primary, task)
        if fallback:
            config.fallback = _config_for(fallback, task)
        registry[task] = config
    return registry


MODEL_REGISTRY: Dict[str, ModelConfig] = _build_registry()


def get_model_config(task: str) -> ModelConfig:
    if task not in MODEL_REGISTRY:
        raise ValueError(f"Unknown task: {task}. Available: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[task]
