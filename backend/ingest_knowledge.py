"""Ingest a small FAQ/knowledge base into the knowledge_chunks table.

Usage:
    python ingest_knowledge.py

This script:
- Chunks provided FAQ docs into segments
- Generates mock embeddings (deterministic based on content)
- Stores embeddings in the knowledge_chunks table
- Is idempotent: skips chunks that already exist (based on content hash)
"""
import hashlib
import os
import time
import json
import psycopg2
from uuid import uuid4

from app.core.config import settings


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


def generate_mock_embedding(text: str, dimension: int = 1536) -> list[float]:
    """Generate a mock embedding vector for the given text.

    In production, this would use the retriever model (OpenAI text-embedding-3-small).
    For MVP, we create a deterministic vector based on the text hash.
    """
    hash_val = int(hashlib.sha256(text.encode('utf-8')).hexdigest(), 16)
    embedding = []
    for i in range(dimension):
        val = ((hash_val >> (i * 8)) & 0xFF) / 255.0
        embedding.append(val - 0.5)  # Center around 0
    return embedding


def format_pg_array(floats: list[float]) -> str:
    """Format a list of floats as a PostgreSQL FLOAT[] array string."""
    return "{" + ",".join(f"{v:.6f}" for v in floats) + "}"


def ingest_knowledge_base():
    """Ingest the FAQ knowledge base into the database."""
    # Calculate which chunks already exist
    conn = psycopg2.connect(settings.DATABASE_URL.replace("+psycopg", ""))
    conn.autocommit = False
    cur = conn.cursor()
    
    # Get existing chunk contents for idempotency check
    cur.execute("SELECT id, content FROM knowledge_chunks")
    existing_chunks = {row[0]: row[1] for row in cur.fetchall()}
    
    new_chunks = []
    
    for doc in FAQ_KNOWLEDGE_BASE:
        content = doc["content"]
        content_hash = compute_content_hash(content)
        
        # Check if chunk already exists (idempotency)
        already_exists = any(
            compute_content_hash(existing) == content_hash 
            for existing in existing_chunks.values()
        )
        if already_exists:
            print(f"Skipping existing chunk (id={doc['id']})")
            continue
        
        # Generate mock embedding
        embedding = generate_mock_embedding(content, dimension=1536)
        # Format as PostgreSQL FLOAT[] array string
        embedding_str = format_pg_array(embedding)
        
        # Prepare chunk data
        chunk_id = str(uuid4())
        meta = {
            "title": doc["title"],
            "source_id": doc["id"],
            "ingested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        meta_json = json.dumps(meta)
        
        new_chunks.append({
            "id": chunk_id,
            "source_id": doc["id"],
            "source_type": doc["source_type"],
            "content": content,
            "embedding": embedding_str,
            "meta_json": meta_json,
        })
        print(f"Prepared chunk: {doc['id']} (embedding dimension: {len(embedding)})")
    
    # Insert new chunks into the database
    if new_chunks:
        for chunk in new_chunks:
            cur.execute(
                "INSERT INTO knowledge_chunks (id, source_id, source_type, content, embedding, meta) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    chunk["id"],
                    chunk["source_id"],
                    chunk["source_type"],
                    chunk["content"],
                    chunk["embedding"],
                    chunk["meta_json"],
                )
            )
        conn.commit()
        print(f"Successfully inserted {len(new_chunks)} new knowledge chunks")
    else:
        print("All chunks already exist - no new chunks inserted")
    
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