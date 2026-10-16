import time
import uuid
from typing import Any, Sequence, Type

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.model_registry import ModelConfig
from app.core.pricing import estimate_cost_usd
from app.core.providers import api_key_for
from app.db.session import SyncSessionLocal
from app.models.base import ProviderCall


def create_llm(config: ModelConfig) -> BaseChatModel:
    api_key = api_key_for(config.provider)
    if not api_key:
        raise ValueError(
            f"No API key configured for provider '{config.provider}'. "
            f"Add the matching key to .env and restart the backend."
        )

    params = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "api_key": api_key,
    }

    if config.provider == "anthropic":
        return ChatAnthropic(**params)
    if config.provider == "openai":
        return ChatOpenAI(**params)
    if config.provider == "mistral":
        from langchain_mistralai import ChatMistralAI

        return ChatMistralAI(**params)
    if config.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(**params)
    raise ValueError(f"Unknown provider: {config.provider}")


def token_usage(message: Any) -> tuple[int, int]:
    """Input/output token counts the provider reported, or ``(0, 0)``.

    LangChain normalises most providers into ``usage_metadata``; a few only fill
    ``response_metadata["token_usage"]``, so both are checked.
    """
    usage = getattr(message, "usage_metadata", None) or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    if input_tokens or output_tokens:
        return input_tokens, output_tokens

    fallback = (getattr(message, "response_metadata", None) or {}).get("token_usage") or {}
    return int(fallback.get("prompt_tokens") or 0), int(fallback.get("completion_tokens") or 0)


def record_provider_call(
    provider: str,
    model: str,
    task: str,
    *,
    latency_ms: int,
    message: Any | None = None,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Persist one provider call with its real tokens, cost and outcome.

    Uses its own sync session so both the synchronous graph nodes and the
    asynchronous routes can record a call without sharing one. Tokens come from
    the provider's own usage report and cost from the price table; an unpriced
    model stores no cost so a missing price cannot look like a measured ``$0``.
    """
    input_tokens, output_tokens = token_usage(message) if message is not None else (0, 0)
    cost = estimate_cost_usd(model, input_tokens, output_tokens)
    with SyncSessionLocal() as db:
        db.add(
            ProviderCall(
                id=uuid.uuid4(),
                provider=provider,
                model=model,
                task=task,
                input_tokens=str(input_tokens),
                output_tokens=str(output_tokens),
                latency_ms=str(latency_ms),
                cost_estimate=None if cost is None else f"{cost:.10f}",
                success=str(success).lower(),
                error=error,
            )
        )
        db.commit()


def invoke_structured_llm(
    config: ModelConfig,
    schema: Type[BaseModel],
    messages: Sequence[tuple[str, str]],
    task: str,
) -> BaseModel:
    """Invoke ``schema``-structured output, falling back to the secondary model.

    ``include_raw`` keeps the underlying message so the provider's real token
    usage is available for cost accounting — ``with_fallbacks`` would hide it.
    Every attempt is recorded, so a failed primary appears as a failure rather
    than being silently retried past the metrics.
    """
    attempts = [config, config.fallback] if config.fallback else [config]
    last_error: Exception | None = None

    for attempt in attempts:
        llm = create_llm(attempt).with_structured_output(schema, include_raw=True)
        start = time.perf_counter()
        try:
            envelope = llm.invoke(list(messages))
        except Exception as exc:
            record_provider_call(
                attempt.provider,
                attempt.model,
                task,
                latency_ms=_elapsed_ms(start),
                success=False,
                error=str(exc),
            )
            last_error = exc
            continue

        parsed = envelope.get("parsed")
        record_provider_call(
            attempt.provider,
            attempt.model,
            task,
            latency_ms=_elapsed_ms(start),
            message=envelope.get("raw"),
            success=parsed is not None,
            error=None if parsed is not None else f"structured parse failed: {envelope.get('parsing_error')}",
        )
        if parsed is not None:
            return parsed
        last_error = ValueError(f"{attempt.model} returned no parsable {schema.__name__}")

    raise last_error or RuntimeError("No model configured for task")


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
