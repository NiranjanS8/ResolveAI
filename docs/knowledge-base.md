# Knowledge Base

The agent grounds its answers in the company's own policy and support
documents. Those documents live in `knowledge/` at the repository root and are
indexed into the `knowledge_chunks` table.

## Where documents live

```
knowledge/
  policies/   -> source_type "policy"
  support/    -> source_type "support"
```

The first folder under `knowledge/` decides the chunk's `source_type`, which is
recorded on every chunk and can be used to filter retrieval. Add new folders and
map them in `SOURCE_TYPE_BY_DIR` in `backend/app/core/knowledge.py` if you want a
meaningful label; anything else becomes `doc`.

Supported formats are Markdown, plain text and HTML. A document's title comes
from its first `#` heading (Markdown), its `<title>` or first `<h1>` (HTML), its
first line (plain text), or its filename as a last resort.

## Re-indexing

Run from `backend/`:

```bash
python ingest_knowledge.py                 # ingest knowledge/
python ingest_knowledge.py --path ../docs  # ingest a different folder
python ingest_knowledge.py --dry-run       # report changes, write nothing
python ingest_knowledge.py --keep-orphans  # do not remove deleted documents
```

Ingestion is idempotent. Each chunk is hashed, so re-running skips unchanged
documents, replaces the chunks of an edited document, and (by default) removes
chunks whose document no longer exists. Chunks written by the feedback loop
(`source_type = "feedback"`) are never pruned.

Point `KNOWLEDGE_DIR` at an external folder to index documents that live outside
this repository.

## How retrieval works

The ticket subject and body are embedded with the same model used at ingestion,
then ranked with pgvector's cosine-distance operator (`<=>`) in
`retrieve_node`. The top `RETRIEVAL_TOP_K` chunks are returned with their
similarity score, and the maximum score drives routing confidence.

The `embedding` column is an unconstrained pgvector `vector`, not `vector(N)`,
because the embedding provider is switchable and each one produces a different
dimension:

| Provider | Model | Dimensions |
| --- | --- | --- |
| Mistral | `mistral-embed` | 1024 |
| Gemini | `models/text-embedding-004` | 768 |
| OpenAI | `text-embedding-3-small` | 1536 |
| none | deterministic local fallback | 1536 |

Retrieval filters on `vector_dims(embedding)` so rows embedded by a different
provider are skipped rather than mismatched. Switching provider therefore means
re-running the ingestion script, not a new migration. For the same reason there
is no ANN index: an index would pin the dimension. At this corpus size exact
search in Postgres is fast, and an index can be added later once the provider is
fixed.

## Schema

`knowledge_chunks` carries `source_id` (the document path), `source_type`,
`doc_title`, `source_path`, `chunk_index`, `content_hash` and `embedding_model`
alongside the chunk `content` and its vector. `content_hash` is what makes
re-ingestion idempotent.
