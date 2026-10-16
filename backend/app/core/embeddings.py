"""Shared embedding function for ingestion and retrieval.

Both the knowledge-base ingestion script and the retrieve node call
``embed_text`` so that indexed vectors and query vectors are produced by the
same model and live in the same vector space. When no usable OpenAI key is
configured it falls back to a deterministic local embedding, which keeps the
whole pipeline runnable offline for the MVP.
"""
import hashlib
import math
from functools import lru_cache

from app.core.config import settings

EMBEDDING_DIM = 1536
EMBEDDING_MODEL = "text-embedding-3-small"


def _looks_like_real_key(key: str | None) -> bool:
    if not key:
        return False
    placeholder_markers = ("your_", "here", "changeme", "xxx")
    lowered = key.lower()
    return len(key) > 20 and not any(marker in lowered for marker in placeholder_markers)


def _deterministic_embedding(text: str, dimension: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic hash-based embedding used when no API key is available."""
    hash_val = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return [(((hash_val >> (i * 8)) & 0xFF) / 255.0) - 0.5 for i in range(dimension)]


@lru_cache(maxsize=1)
def _openai_embeddings():
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def embed_text(text: str) -> list[float]:
    """Embed text for storage or querying."""
    if _looks_like_real_key(settings.OPENAI_API_KEY):
        try:
            return _openai_embeddings().embed_query(text)
        except Exception:
            pass
    return _deterministic_embedding(text)


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
