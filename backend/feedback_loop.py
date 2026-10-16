"""Feedback Loop — Agent corrections make the system measurably better over time.

Pulls agent_feedback rows the operator has explicitly approved, re-embeds them,
and adds them to knowledge_chunks as "resolved ticket" examples.

Approval is not implicit. An agent edit is evidence that a draft was wrong; it is
not evidence that the edit is correct or safe to serve to every future customer,
and an agent can be talked into writing the wrong thing. So nothing is indexed
until a human names the feedback row (``--approve``), and each promoted chunk
records the customer it came from, so retrieval can keep it away from everyone
else's tickets.

Usage:
    python feedback_loop.py                        # list candidates, index nothing
    python feedback_loop.py --approve <id> [<id>]  # index exactly those

Idempotent: skips chunks that already exist (based on content hash).
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import psycopg2

from app.core.config import settings
from app.core.embeddings import embed_text
from app.core.knowledge import embedding_model_label

# Word-set overlap below this counts as a significant edit rather than rewording.
SIGNIFICANT_EDIT_OVERLAP = 0.7


def compute_content_hash(content: str) -> str:
    """Compute a hash for content to check idempotency."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def format_pg_array(floats: list[float]) -> str:
    """Format a list of floats as a pgvector literal, e.g. ``[0.1,0.2]``."""
    return "[" + ",".join(f"{v:.6f}" for v in floats) + "]"


def _is_significant_edit(original_draft: str, edited_response: str) -> tuple[bool, float]:
    """Whether the agent changed the draft materially, and the word-set overlap."""
    original_words = set(original_draft.lower().split())
    edited_words = set(edited_response.lower().split())
    union = original_words | edited_words
    if not union:
        return True, 0.0
    overlap = len(original_words & edited_words) / len(union)
    return overlap < SIGNIFICANT_EDIT_OVERLAP, overlap


def _candidates(cur) -> list[tuple]:
    """Recent feedback rows that would promote, with their ticket's customer."""
    cur.execute(
        """
        SELECT f.id, f.original_draft, f.edited_response, f.agent_id, f.created_at,
               t.customer_id
        FROM agent_feedback f
        JOIN tickets t ON t.id = f.ticket_id
        ORDER BY f.created_at DESC
        LIMIT 50
        """
    )
    return cur.fetchall()


def _significant(cur) -> list[tuple]:
    """The candidates an edit actually changed, as (row..., overlap)."""
    ready = []
    for row in _candidates(cur):
        feedback_id, original_draft, edited_response = row[0], row[1], row[2]
        if not original_draft or not edited_response:
            print(f"Skipping feedback {feedback_id}: empty original or edited draft")
            continue
        significant, overlap = _is_significant_edit(original_draft, edited_response)
        if not significant:
            print(f"Skipping feedback {feedback_id}: edit not significant (overlap={overlap:.2f})")
            continue
        ready.append((*row, overlap))
    return ready


def _report_candidates(ready: list[tuple]) -> None:
    """Show what could be promoted, so the operator approves from evidence."""
    print(f"{len(ready)} significant edit(s) are available for promotion:")
    for feedback_id, _original, edited, agent_id, _created, customer_id, overlap in ready:
        preview = " ".join(edited.split())[:70]
        print(f"  {feedback_id}  customer={customer_id}  agent={agent_id}  overlap={overlap:.2f}")
        print(f"    {preview!r}")
    print("\nRe-run with --approve <id> [...] to index exactly those entries.")


def _prepare_chunk(row: tuple, approved_by: str, existing_hashes: set[str]) -> dict | None:
    """Build the knowledge chunk for one approved feedback row, or None to skip."""
    feedback_id, _original, edited_response, agent_id, created_at, customer_id, _overlap = row

    content_hash = compute_content_hash(edited_response)
    if content_hash in existing_hashes:
        print(f"Skipping feedback {feedback_id}: chunk already exists in knowledge_base")
        return None

    source_id = f"feedback_{feedback_id}"
    return {
        "id": str(uuid4()),
        "source_id": source_id,
        "source_type": "feedback",
        "content": edited_response,
        "embedding": format_pg_array(embed_text(edited_response)),
        "embedding_model": embedding_model_label(),
        "meta": {
            "title": f"Feedback entry - Agent {agent_id}",
            "source_id": source_id,
            "source_type": "feedback",
            "feedback_id": str(feedback_id),
            # Retrieval serves a chunk only to the customer it came from.
            "customer_id": customer_id,
            "approved_by": approved_by,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "ingested_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
        },
    }


def _insert_chunks(conn, cur, chunks: list[dict]) -> None:
    for chunk in chunks:
        cur.execute(
            """INSERT INTO knowledge_chunks
                   (id, source_id, source_type, content, embedding, embedding_model, meta)
               VALUES (%s, %s, %s, %s, %s::vector, %s, %s)""",
            (
                chunk["id"],
                chunk["source_id"],
                chunk["source_type"],
                chunk["content"],
                chunk["embedding"],
                chunk["embedding_model"],
                json.dumps(chunk["meta"]),
            ),
        )
    conn.commit()
    print(f"Successfully inserted {len(chunks)} approved feedback knowledge chunks")


def _retrieval_check(cur) -> None:
    """Report what each test query now matches, as a crude before/after view."""
    print("\n--- Retrieval Quality Check ---")
    for query in ["refund", "shipping", "password", "billing"]:
        cur.execute(
            """SELECT source_id, content
               FROM knowledge_chunks
               WHERE content ILIKE %s
               ORDER BY created_at DESC
               LIMIT 3""",
            (f"%{query}%",),
        )
        rows = cur.fetchall()
        print(f"Query '{query}': {len(rows)} matches found")
        for source_id, content in rows:
            print(f"  - {source_id}: {(content or '')[:50]}...")


def feedback_loop(approved_ids: list[str] | None = None, approved_by: str = "operator") -> None:
    """Index the feedback rows the operator approved; never index anything else."""
    approved = {str(identifier) for identifier in (approved_ids or [])}

    conn = psycopg2.connect(settings.DATABASE_URL.replace("+psycopg", ""))
    conn.autocommit = False
    cur = conn.cursor()

    try:
        ready = _significant(cur)
        print(f"Significant edits considered: {len(ready)}")

        if not approved:
            _report_candidates(ready)
            print("\n--- Nothing indexed: no approval given ---")
            return

        unknown = approved - {str(row[0]) for row in ready}
        if unknown:
            print(f"Not promoting {sorted(unknown)}: no significant edit found for those ids")

        cur.execute("SELECT content FROM knowledge_chunks")
        existing_hashes = {compute_content_hash(row[0]) for row in cur.fetchall()}

        chunks = []
        for row in ready:
            if str(row[0]) not in approved:
                continue
            chunk = _prepare_chunk(row, approved_by, existing_hashes)
            if chunk is None:
                continue
            existing_hashes.add(compute_content_hash(chunk["content"]))
            chunks.append(chunk)
            print(f"Prepared feedback chunk {chunk['meta']['feedback_id']} "
                  f"({len(chunk['content'])} chars, customer={chunk['meta']['customer_id']})")

        if chunks:
            _insert_chunks(conn, cur, chunks)
        else:
            print("No new feedback chunks to insert")

        _retrieval_check(cur)
    finally:
        cur.close()
        conn.close()

    print("\n--- Feedback Loop Complete ---")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote explicitly approved agent feedback into the knowledge base."
    )
    parser.add_argument("--approve", nargs="+", metavar="FEEDBACK_ID",
                        help="feedback ids to promote; without this nothing is indexed")
    parser.add_argument("--by", default="operator", help="who approved the promotion")
    args = parser.parse_args()

    print("=" * 60)
    print("ResolveAI Feedback Loop")
    print("=" * 60)
    print("This script pulls agent corrections and feeds them back")
    print("into the knowledge base to improve future retrieval.")
    print()
    feedback_loop(args.approve, args.by)
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
