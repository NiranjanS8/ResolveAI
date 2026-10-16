"""Ingest a small FAQ/knowledge base into the knowledge_chunks table.

Usage:
    python ingest_knowledge.py

This script:
- Chunks provided FAQ docs into segments
- Generates embeddings via the shared embedding function (Gemini, Mistral or
  OpenAI when a key is configured, deterministic local vectors otherwise)
- Stores embeddings in the knowledge_chunks table
- Is idempotent: skips chunks that already exist and already use the current
  embedding dimension, re-embedding them when the embedding provider changes
"""
import hashlib
import os
import time
import json
import psycopg2
from uuid import uuid4

from app.core.config import settings
from app.core.embeddings import embed_text, embedding_dimension


# Simple FAQ knowledge base for MVP (5 docs)
FAQ_KNOWLEDGE_BASE: list[dict] = [
    {
        "id": "faq_1",
        "title": "Refund Policy",
        "content": "Our refund policy allows returns within 30 days of purchase for a full refund, provided the product is in original condition. Refunds are processed within 5-7 business days.",
        "source_type": "policy",
    },
    {
        "id": "faq_2",
        "title": "Shipping Information",
        "content": "Standard shipping takes 5-7 business days. Express shipping takes 2-3 business days. Orders are shipped from our warehouse in New York.",
        "source_type": "policy",
    },
    {
        "id": "faq_3",
        "title": "Password Reset",
        "content": "To reset your password, click 'Forgot Password' on the login page and enter your email address. You'll receive a reset link within minutes. If you don't receive the email, check your spam folder.",
        "source_type": "support",
    },
    {
        "id": "faq_4",
        "title": "Billing Cycle",
        "content": "Billing occurs monthly on the anniversary of your subscription start date. You can view your billing history in the account settings. Cancel anytime before your next billing cycle.",
        "source_type": "policy",
    },
    {
        "id": "faq_5",
        "title": "Technical Support",
        "content": "For technical issues, please describe the problem including error messages, what you were doing when it occurred, and your browser/device information. Our typical response time is within 24 hours.",
        "source_type": "support",
    },
]


def compute_content_hash(content: str) -> str:
    """Compute a hash for content to check idempotency."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def format_pg_array(floats: list[float]) -> str:
    """Format a list of floats as a PostgreSQL FLOAT[] array string."""
    return "{" + ",".join(f"{v:.6f}" for v in floats) + "}"


def ingest_knowledge_base():
    """Ingest the FAQ knowledge base into the database."""
    target_dim = embedding_dimension()

    conn = psycopg2.connect(settings.DATABASE_URL.replace("+psycopg", ""))
    conn.autocommit = False
    cur = conn.cursor()

    # Existing chunks keyed by content hash, carrying the dimension of the
    # stored embedding so we can re-embed when the embedding provider changes.
    cur.execute(
        "SELECT id, content, coalesce(array_length(embedding, 1), 0) FROM knowledge_chunks"
    )
    existing_chunks = {
        compute_content_hash(content): (chunk_id, int(dim or 0))
        for chunk_id, content, dim in cur.fetchall()
    }

    inserted = 0
    updated = 0

    for doc in FAQ_KNOWLEDGE_BASE:
        content = doc["content"]
        content_hash = compute_content_hash(content)
        current = existing_chunks.get(content_hash)

        if current and current[1] == target_dim:
            print(f"Skipping existing chunk (id={doc['id']})")
            continue

        # Generate embedding using the shared embedding function so that
        # indexed vectors match query vectors at retrieval time.
        embedding = embed_text(content)
        embedding_str = format_pg_array(embedding)
        meta_json = json.dumps({
            "title": doc["title"],
            "source_id": doc["id"],
            "ingested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        if current:
            cur.execute(
                "UPDATE knowledge_chunks SET embedding = %s, meta = %s WHERE id = %s",
                (embedding_str, meta_json, current[0]),
            )
            updated += 1
            print(f"Re-embedded chunk: {doc['id']} ({current[1]} -> {len(embedding)} dims)")
        else:
            cur.execute(
                "INSERT INTO knowledge_chunks (id, source_id, source_type, content, embedding, meta) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (str(uuid4()), doc["id"], doc["source_type"], content, embedding_str, meta_json),
            )
            inserted += 1
            print(f"Prepared chunk: {doc['id']} (embedding dimension: {len(embedding)})")

    conn.commit()
    if inserted or updated:
        print(f"Knowledge base updated: {inserted} inserted, {updated} re-embedded")
    else:
        print("All chunks already exist and are up to date - nothing to do")

    cur.close()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("ResolvAI Knowledge Base Ingestion")
    print("=" * 60)
    print(f"Knowledge base items: {len(FAQ_KNOWLEDGE_BASE)}")
    print()
    ingest_knowledge_base()
    print()
    print("=" * 60)
    print("Ingestion complete!")
    print("=" * 60)