"""Ingestion smoke test: loader, chunker, idempotency and pgvector retrieval.

Run from the backend directory:

    python test_knowledge_ingestion.py

Exits non-zero if any check fails.
"""
import sys

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text as sq_text

from app.core.knowledge import ingest, knowledge_dir, load_documents
from app.core.embeddings import embed_text
from app.db.session import sync_engine


def check(label: str, condition: bool, detail: str = "") -> bool:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" - {detail}" if detail else ""))
    return condition


def main() -> int:
    results: list[bool] = []

    documents = load_documents()
    results.append(check("loader finds documents", len(documents) >= 5, f"{len(documents)} docs"))
    results.append(
        check(
            "documents carry titles and paths",
            all(doc.title and doc.source_path for doc in documents),
        )
    )
    results.append(
        check(
            "source types derived from folders",
            {doc.source_type for doc in documents} >= {"policy", "support"},
            str(sorted({doc.source_type for doc in documents})),
        )
    )

    first = ingest(prune=True)
    results.append(check("first ingest writes chunks", first.chunks_total > 0, f"{first.chunks_total} chunks"))
    results.append(
        check(
            "each document yields at least one chunk",
            first.chunks_total >= first.documents,
            f"{first.chunks_total} chunks for {first.documents} docs",
        )
    )

    second = ingest(prune=True)
    results.append(
        check(
            "second ingest is idempotent",
            second.inserted == 0 and second.unchanged == first.chunks_total and second.pruned == 0,
            f"inserted={second.inserted} unchanged={second.unchanged} pruned={second.pruned}",
        )
    )

    query_embedding = embed_text("I want a refund for a damaged item that arrived late")
    vector_literal = "[" + ",".join(f"{value:.8f}" for value in query_embedding) + "]"
    with sync_engine.connect() as conn:
        rows = conn.execute(
            sq_text("""
                SELECT doc_title, source_id, 1 - (embedding <=> CAST(:query AS vector)) AS score
                FROM knowledge_chunks
                WHERE embedding IS NOT NULL
                  AND vector_dims(embedding) = :dimension
                ORDER BY embedding <=> CAST(:query AS vector)
                LIMIT 3
            """),
            {"query": vector_literal, "dimension": len(query_embedding)},
        ).fetchall()

    results.append(check("pgvector search returns rows", len(rows) == 3, f"{len(rows)} rows"))
    if rows:
        top_title, top_source, top_score = rows[0]
        print(f"       top match: {top_title} ({top_source}) score={float(top_score):.4f}")
        results.append(
            check("top match is a refund/shipping document", "refund" in top_source or "shipping" in top_source)
        )

    print()
    passed = sum(1 for result in results if result)
    print(f"{passed}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
