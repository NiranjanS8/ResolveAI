from typing import Dict, Any
from pydantic import BaseModel


class ModelConfig(BaseModel):
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1000
    fallback: "ModelConfig | None" = None


MODEL_REGISTRY: Dict[str, ModelConfig] = {
    "classifier": ModelConfig(
        provider="anthropic",
        model="claude-3-haiku-20240307",
        temperature=0.0,
        max_tokens=500,
        fallback=ModelConfig(
            provider="openai",
            model="gpt-4o-mini",
            temperature=0.0,
            max_tokens=500,
        ),
    ),
    "retriever": ModelConfig(
        provider="openai",
        model="text-embedding-3-small",
        temperature=0.0,
    ),
    "drafter": ModelConfig(
        provider="anthropic",
        model="claude-3-sonnet-20240229",
        temperature=0.3,
        max_tokens=1000,
        fallback=ModelConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
        ),
    ),
    "decider": ModelConfig(
        provider="anthropic",
        model="claude-3-haiku-20240307",
        temperature=0.0,
        max_tokens=500,
        fallback=ModelConfig(
            provider="openai",
            model="gpt-4o-mini",
            temperature=0.0,
            max_tokens=500,
        ),
    ),
}


def get_model_config(task: str) -> ModelConfig:
    if task not in MODEL_REGISTRY:
        raise ValueError(f"Unknown task: {task}. Available: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[task]