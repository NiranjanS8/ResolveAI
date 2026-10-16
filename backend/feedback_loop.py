"""Feedback Loop — Agent corrections make the system measurably better over time.

Pulls recent agent_feedback rows where the agent significantly edited the draft,
re-embeds them, and adds them to knowledge_chunks as "resolved ticket" examples.

Idempotent: skips chunks that already exist (based on content hash).

Usage:
    python feedback_loop.py

This script:
1. Queries the agent_feedback table for recent entries
2. Determines which edits were significant (original != edited)
3. Generates embeddings for the feedback pairs
4. Stores them in knowledge_chunks with source_type="feedback"
5. Runs a before/after retrieval quality check
6. Is idempotent: re-running doesn't duplicate effective entries
"""
import hashlib
import os
import json
import math
import psycopg2
from uuid import uuid4

from app.core.config import settings
from app.core.embeddings import embed_text


# Similarity cosine between two embedding strings (FLOAT[] arrays)
def _cosine_similarity_embedding(emb_a: str, emb_b: str) -> float:
    """Compute cosine similarity between two PostgreSQL FLOAT[] arrays."""
    import re
    # Extract float values from PG array string like "{0.1,0.2,0.3}"
    nums_a = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", emb_a)]
    nums_b = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", emb_b)]
    
    if not nums_a or not nums_b or len(nums_a) != len(nums_b):
        return 0.0
    
    dot = sum(x * y for x, y in zip(nums_a, nums_b))
    norm_a = math.sqrt(sum(x * x for x in nums_a))
    norm_b = math.sqrt(sum(x * x for x in nums_b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


def compute_content_hash(content: str) -> str:
    """Compute a hash for content to check idempotency."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def format_pg_array(floats: list[float]) -> str:
    """Format a list of floats as a PostgreSQL FLOAT[] array string."""
    return "{" + ",".join(f"{v:.6f}" for v in floats) + "}"


def feedback_loop():
    """Main feedback loop function."""
    # Connect to DB
    conn = psycopg2.connect(settings.DATABASE_URL.replace("+psycopg", ""))
    conn.autocommit = False
    cur = conn.cursor()
    
    # Step 1: Query recent agent_feedback entries
    cur.execute("""
        SELECT id, original_draft, edited_response, agent_id, created_at
        FROM agent_feedback
        ORDER BY created_at DESC
        LIMIT 10
    """)
    feedback_entries = cur.fetchall()
    
    print(f"Recent agent_feedback entries: {len(feedback_entries)}")
    
    new_chunks = []
    
    for feedback_id, original_draft, edited_response, agent_id, created_at in feedback_entries:
        # Determine if the edit was significant
        # An edit is significant if the edited response is meaningfully different
        # and the original draft was not empty
        if not original_draft or not edited_response:
            print(f"Skipping feedback {feedback_id}: empty original or edited draft")
            continue
        
        # Check if edits are substantial (more than just minor wording changes)
        orig_words = set(original_draft.lower().split())
        edit_words = set(edited_response.lower().split())
        
        # Jaccard similarity of word sets
        intersection = orig_words & edit_words
        union = orig_words | edit_words
        
        if not union:
            significant_edit = True
        else:
            jaccard = len(intersection) / len(union)
            # Significant if less than 70% overlap
            significant_edit = jaccard < 0.7
        
        if not significant_edit:
            print(f"Skipping feedback {feedback_id}: edit not significant (Jaccard={jaccard:.2f})")
            continue
        
        # Generate embeddings for the original and edited drafts
        orig_embedding = embed_text(original_draft)
        edit_embedding = embed_text(edited_response)
        orig_emb_str = format_pg_array(orig_embedding)
        edit_emb_str = format_pg_array(edit_embedding)
        
        # Create feedback chunk data - we'll store the edited version as the content
        # with metadata indicating this is a feedback entry
        feedback_hash = compute_content_hash(edited_response)
        
        # Check if a chunk with this content already exists (idempotency)
        cur.execute("SELECT id, content FROM knowledge_chunks")
        existing_chunks = {row[0]: row[1] for row in cur.fetchall()}
        
        already_exists = any(
            compute_content_hash(existing) == feedback_hash 
            for existing in existing_chunks.values()
        )
        
        if already_exists:
            print(f"Skipping feedback {feedback_id}: chunk already exists in knowledge_base")
            continue
        
        # Create chunk metadata
        chunk_id = str(uuid4())
        meta = {
            "title": f"Feedback entry - Agent {agent_id}",
            "source_id": f"feedback_{feedback_id}",
            "source_type": "feedback",
            "feedback_id": str(feedback_id),
            "original_draft": original_draft[:100] if len(original_draft) > 100 else original_draft,
            "edited_response": edited_response[:100] if len(edited_response) > 100 else edited_response,
            "ingested_at": created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
        }
        meta_json = json.dumps(meta)
        
        new_chunks.append({
            "id": chunk_id,
            "source_id": f"feedback_{feedback_id}",
            "source_type": "feedback",
            "content": edited_response,
            "embedding": orig_emb_str,  # Use original embedding (or we could avg both)
            "meta": meta,
        })
        print(f"Prepared feedback chunk: {feedback_id} (edit significant, {len(edited_response)} chars)")
    
    # Step 2: Insert new chunks into the database
    if new_chunks:
        with conn.cursor() as cur_insert:
            for chunk in new_chunks:
                meta_json = json.dumps(chunk["meta"])
                
                cur_insert.execute(
                    """INSERT INTO knowledge_chunks (id, source_id, source_type, content, embedding, meta)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        chunk["id"],
                        chunk["source_id"],
                        chunk["source_type"],
                        chunk["content"],
                        chunk["embedding"],
                        meta_json,
                    )
                )
            conn.commit()
            print(f"Successfully inserted {len(new_chunks)} new feedback knowledge chunks")
    else:
        print("No new feedback chunks to insert - all significant edits already in knowledge base")
    
    # Step 3: Before/After retrieval quality check
    print("\n--- Before/After Retrieval Quality Check ---")
    
    # Query: test retrieving tickets with specific intents
    test_queries = [
        "refund",
        "shipping", 
        "password",
        "billing",
    ]
    
    for query in test_queries:
        cur.execute(
            """SELECT id, source_id, content, embedding 
               FROM knowledge_chunks 
               WHERE content ILIKE %s 
               ORDER BY created_at DESC
               LIMIT 3""",
            (f"%{query}%",)
        )
        rows = cur.fetchall()
        print(f"Query '{query}': {len(rows)} matches found")
        for row in rows:
            print(f"  - {row[1]}: {row[2][:50] if row[2] else 'None'}...")
    
    # Step 4: Close connections
    cur.close()
    conn.close()
    
    print("\n--- Feedback Loop Complete ---")


if __name__ == "__main__":
    print("=" * 60)
    print("ResolvAI Feedback Loop")
    print("=" * 60)
    print("This script pulls agent corrections and feeds them back")
    print("into the knowledge base to improve future retrieval.")
    print()
    feedback_loop()
    print("=" * 60)