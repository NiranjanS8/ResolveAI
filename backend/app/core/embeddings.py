"""Shared embedding function for ingestion and retrieval.

Both the knowledge-base ingestion script and the retrieve node call
``embed_text`` so that indexed vectors and query vectors are produced by the
same model and live in the same vector space. When no usable embedding key is
configured it falls back to a deterministic local embedding, which keeps the
whole pipeline runnable offline for the MVP.
"""
import hashlib
import math
from functools import lru_cache

from app.core.config import settings
from app.core.providers import EMBEDDING_PROVIDERS, api_key_for, select_provider

LOCAL_EMBEDDING_DIM = 1536

# provider -> (model, dimension). Dimensions are fixed per model because stored
# vectors must stay comparable with query vectors.
EMBEDDING_MODELS: dict[str, tuple[str, int]] = {
    "gemini": ("models/text-embedding-004", 768),
    "mistral": ("mistral-embed", 1024),
    "openai": ("text-embedding-3-small", 1536),
}


def active_provider() -> str | None:
    return select_provider(settings.EMBEDDING_PROVIDER, EMBEDDING_PROVIDERS)


def embedding_dimension() -> int:
    provider = active_provider()
    return EMBEDDING_MODELS[provider][1] if provider else LOCAL_EMBEDDING_DIM


def _deterministic_embedding(text: str, dimension: int) -> list[float]:
    """Deterministic hash-based embedding used when no API key is available."""
    hash_val = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return [(((hash_val >> (i * 8)) & 0xFF) / 255.0) - 0.5 for i in range(dimension)]


@lru_cache(maxsize=len(EMBEDDING_MODELS))
def _embedding_client(provider: str):
    model = EMBEDDING_MODELS[provider][0]
    api_key = api_key_for(provider)
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model, api_key=api_key)
    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(model=model, api_key=api_key)
    if provider == "mistral":
        from langchain_mistralai import MistralAIEmbeddings

        return MistralAIEmbeddings(model=model, api_key=api_key)
    raise ValueError(f"Unknown embedding provider: {provider}")


def embed_text(text: str) -> list[float]:
    """Embed text for storage or querying."""
    provider = active_provider()
    if provider:
        try:
            return _embedding_client(provider).embed_query(text)
        except Exception:
            pass
    return _deterministic_embedding(text, LOCAL_EMBEDDING_DIM)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
