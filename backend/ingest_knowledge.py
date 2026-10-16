"""CLI: (re)index the ResolveAI knowledge base into pgvector.

Documents are read from the repository's ``knowledge/`` folder unless
``--path`` points somewhere else. Supported formats: Markdown, plain text and
HTML.

Usage:
    python ingest_knowledge.py
    python ingest_knowledge.py --path ../knowledge
    python ingest_knowledge.py --dry-run
    python ingest_knowledge.py --keep-orphans

Re-running is idempotent: unchanged documents are skipped, edited documents
have their chunks replaced, and (unless ``--keep-orphans``) chunks whose
document no longer exists are pruned.
"""
import argparse
from pathlib import Path

from app.core.knowledge import ingest, knowledge_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the ResolveAI knowledge base.")
    parser.add_argument(
        "--path",
        default=None,
        help="Documents folder (defaults to the repository knowledge/ directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing anything.",
    )
    parser.add_argument(
        "--keep-orphans",
        action="store_true",
        help="Keep chunks whose source document no longer exists.",
    )
    args = parser.parse_args()

    root = Path(args.path).expanduser().resolve() if args.path else knowledge_dir()

    print("=" * 60)
    print("ResolveAI Knowledge Base Ingestion")
    print("=" * 60)
    print(f"Documents folder : {root}")
    print()

    report = ingest(root, prune=not args.keep_orphans, dry_run=args.dry_run)

    print(f"Documents        : {report.documents}")
    print(f"Chunks           : {report.chunks_total}")
    print(f"Inserted         : {report.inserted}")
    print(f"Unchanged        : {report.unchanged}")
    print(f"Pruned           : {report.pruned}")
    print(f"Embedding model  : {report.embedding_model} ({report.dimension} dims)")
    print()
    if args.dry_run:
        print("Dry run - nothing was written.")
    elif not (report.inserted or report.pruned):
        print("Knowledge base already up to date - nothing to do.")
    else:
        print("Ingestion complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
