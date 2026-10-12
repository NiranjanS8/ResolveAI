import time
import uuid
from typing import Any, Dict, Type
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from app.models.base import ProviderCall
from app.core.model_registry import get_model_config, ModelConfig
from app.core.config import settings


def create_llm(config: ModelConfig) -> BaseChatModel:
    if config.provider == "anthropic":
        return ChatAnthropic(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    elif config.provider == "openai":
        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    else:
        raise ValueError(f"Unknown provider: {config.provider}")


async def log_provider_call(
    db: AsyncSession,
    provider: str,
    model: str,
    task: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    cost_estimate: float = 0.0,
    success: bool = True,
    error: str | None = None,
) -> None:
    call = ProviderCall(
        id=uuid.uuid4(),
        provider=provider,
        model=model,
        task=task,
        input_tokens=str(input_tokens),
        output_tokens=str(output_tokens),
        latency_ms=str(latency_ms),
        cost_estimate=str(cost_estimate),
        success=str(success).lower(),
        error=error,
    )
    db.add(call)
    await db.commit()


async def ainvoke_with_fallback(
    primary_config: ModelConfig,
    fallback_config: ModelConfig | None,
    messages: list,
    output_schema: Type[BaseModel],
    db: AsyncSession,
    task: str,
) -> tuple[BaseModel, str, str, int, int]:
    primary_llm = create_llm(primary_config)
    structured_llm = primary_llm.with_structured_output(output_schema)
    
    start = time.perf_counter()
    try:
        result = await structured_llm.ainvoke(messages)
        latency_ms = int((time.perf_counter() - start) * 1000)
        await log_provider_call(
            db, primary_config.provider, primary_config.model, task,
            latency_ms=latency_ms, success=True,
        )
        return result, primary_config.provider, primary_config.model, 0, 0
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        await log_provider_call(
            db, primary_config.provider, primary_config.model, task,
            latency_ms=latency_ms, success=False, error=str(e),
        )
        
        if fallback_config:
            fallback_llm = create_llm(fallback_config)
            structured_fallback = fallback_llm.with_structured_output(output_schema)
            
            start = time.perf_counter()
            try:
                result = await structured_fallback.ainvoke(messages)
                latency_ms = int((time.perf_counter() - start) * 1000)
                await log_provider_call(
                    db, fallback_config.provider, fallback_config.model, task,
                    latency_ms=latency_ms, success=True,
                )
                return result, fallback_config.provider, fallback_config.model, 0, 0
            except Exception as e2:
                latency_ms = int((time.perf_counter() - start) * 1000)
                await log_provider_call(
                    db, fallback_config.provider, fallback_config.model, task,
                    latency_ms=latency_ms, success=False, error=str(e2),
                )
                raise
        raise