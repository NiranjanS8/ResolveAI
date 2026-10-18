# ResolveAI

**An AI customer-support agent that decides how far it is allowed to go, and can prove why.**

A ticket arrives. The agent classifies it, retrieves the relevant company policy, and scores its own
confidence. A confident answer is sent automatically. A shaky answer becomes a draft that a human
approves, edits, or rejects. An unclear ticket goes straight to a person. Every action the agent can take
is allow-listed and capped in code, and every decision is written to an audit trail that the console
renders next to the ticket.

<!-- TODO: add a screenshot or short GIF of the console at docs/assets/console.png
![ResolveAI agent console](docs/assets/console.png) -->

## Features

- **Confidence-based routing.** Each ticket is routed to auto-resolve, human review, or escalation using
  `classifier_confidence * retrieval_relevance` and per-intent thresholds.
- **Human review that survives restarts.** Review is a LangGraph `interrupt()` persisted by a Postgres
  checkpointer, with approve, edit, and reject actions.
- **Guardrails in code, not prompts.** An action allow-list, a hard refund cap, and a check that blocks
  drafts from promising actions the system did not take.
- **Untrusted-input handling.** Hidden HTML and CSS-hidden text are stripped before the model reads a
  message, and the rest arrives fenced as data. The raw message is kept verbatim as evidence.
- **One outbound boundary.** Every agent, AI, and system message is converted to plain text and logged by
  a single function, so what a reviewer approves is exactly what is sent.
- **Audit trail and decision trace.** Decisions and actions are recorded and shown next to the ticket.
- **Live analytics.** Deflection rate, time to first reply, cost per ticket, provider health, and draft
  acceptance are computed from the real tables, not precomputed.
- **Retrieval-augmented answers.** Policy and support documents are indexed with pgvector.
- **Feedback loop with a gate.** Agent edits enter retrieval only after explicit approval.
- **Postgres-backed job queue.** `FOR UPDATE SKIP LOCKED` claiming with retries, backoff, and leases; no
  separate broker.
- **Multiple model providers** through LangChain: Anthropic, OpenAI, Mistral, and Google Gemini.

## How it works

```mermaid
flowchart LR
    UI[React console] -->|REST| API[FastAPI]
    API -->|enqueue| Q[(Postgres job queue)]
    Q --> W[Worker]
    W --> G

    subgraph G[LangGraph ticket graph]
        C[classify] --> R[retrieve] --> D{decide}
        D -->|high| AR[auto_resolve]
        D -->|medium| DR[draft_for_review]
        D -->|low| ES[escalate]
    end

    DR -.->|interrupt| UI
    UI -.->|approve / edit / reject| API
    G --> DB[(Postgres + pgvector)]
```

`POST /api/v1/tickets` writes the ticket and a job in one transaction and returns immediately. A worker
claims the job and runs the graph.

```
relevance     = max(similarity of retrieved chunks)     # 0.0 when nothing was retrieved
routing_score = classifier_confidence * relevance
```

| Decision | Condition |
|---|---|
| `auto_resolve` | `routing_score >= high` for the ticket's intent |
| `draft_for_review` | `routing_score >= medium` |
| `escalate` | otherwise, including when no chunk was retrieved |

An answer with no supporting document scores zero and escalates, so the agent never answers from its own
idea of company policy. Thresholds, node details, and the rest of the design are in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.136, Python 3.14, SQLAlchemy 2.0, psycopg 3, Alembic |
| Orchestration | LangGraph 1.2 with a Postgres checkpointer |
| Models | LangChain over Anthropic, OpenAI, Mistral, Google Gemini |
| Database | PostgreSQL 16 with pgvector |
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4, IBM Plex |
| CI | GitHub Actions |

The frontend uses no chart, component, or state-management library.

## Quickstart

**Requirements:** Python 3.14, Node.js 20.19+ or 22.12+, Docker, and an API key for at least one of
Anthropic, OpenAI, Mistral, or Gemini.

```bash
# 1. Start Postgres (pgvector image, host port 5433)
docker compose -f infra/docker-compose.yml up -d

# 2. Configure: copy the template and add a provider key
cp .env.example .env

# 3. Install and migrate
cd backend
pip install -r requirements.txt
python -m alembic -c alembic/alembic.ini upgrade head

# 4. Index the knowledge base
python ingest_knowledge.py

# 5. Run the API and worker (http://localhost:8000)
python run.py
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000
```

Check that dependencies are healthy:

```bash
curl http://localhost:8000/api/v1/health
```

A healthy response has `"status": "ok"`. An unreachable database returns `503` with
`"status": "degraded"`.

Optional: `python seed_tickets.py` replays ten curated tickets through the real graph so the queue and
analytics have content. It calls a model, so it needs a key.

## Configuration

All settings live in the repository-root `.env`. Defaults are in `backend/app/core/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | See `.env` example below | PostgreSQL connection. |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `MISTRAL_API_KEY`, `GEMINI_API_KEY` | unset | Provider credentials. `GOOGLE_API_KEY` is accepted as a Gemini alias. |
| `LLM_PROVIDER_ORDER` | unset | Comma-separated preference; otherwise the first configured key wins. |
| `EMBEDDING_PROVIDER` | unset | Embedding provider. Changing it requires re-running ingestion. |
| `WORKER_ENABLED` | `true` | Run the in-process queue worker. |
| `WORKER_POLL_SECONDS` | `1` | Worker poll interval. |
| `JOB_MAX_ATTEMPTS` | `3` | Attempts before a job is marked failed. |
| `JOB_LEASE_SECONDS` | `300` | When a running job is considered abandoned and reclaimed. |
| `RETRIEVAL_TOP_K` | `5` | Chunks retrieved per ticket. |
| `KNOWLEDGE_CHUNK_SIZE` / `KNOWLEDGE_CHUNK_OVERLAP` | `900` / `150` | Chunking for ingestion. |
| `KNOWLEDGE_DIR` | empty (repo-root `knowledge/`) | Where ingestion reads from. |
| `BACKEND_CORS_ORIGINS` | `localhost:3000`, `localhost:5173` | Allowed console origins. |
| `SQL_ECHO` | `false` | SQL statement logging. |
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Frontend API base. |

**`.env` default:**

```env
DATABASE_URL=postgresql+psycopg://resolveai:resolveai@localhost:5433/resolveai
```

## Scripts

Run from `backend/` unless noted.

| Command | What it does |
|---|---|
| `python run.py` | Starts the API and the queue worker on port 8000. |
| `python ingest_knowledge.py` | Indexes `knowledge/` into `knowledge_chunks`. Idempotent. Flags: `--path`, `--dry-run`, `--keep-orphans`. |
| `python seed_tickets.py` | Replays ten curated tickets through the real graph. Flags: `--reset`, `--prune-only`. |
| `python analytics_dashboard.py` | Prints the analytics snapshot. Flag: `--range {24h,7d,30d}`. |
| `python feedback_loop.py` | Lists significant agent edits. Indexes nothing unless you pass `--approve <id>` (plus `--by <name>`). |
| `npm run dev` / `build` / `lint` (in `frontend/`) | Dev server, type-check plus production build, and oxlint. |

## Testing and CI

Run from `backend/`.

| Suite | Command | Needs DB | Needs key | Covers |
|---|---|---|---|---|
| Prompt safety | `python test_prompt_safety.py` | yes | no | Prompt boundary, neutralizer, fences, routing guards. `--offline` skips database-backed checks; `--live` adds an opt-in provider probe. |
| Text format | `python test_text_format.py` | yes | no | Sanitizer, email HTML escaping, round trip through the send boundary. |
| Analytics | `python test_analytics.py` | yes | no | Exact metric arithmetic against an isolated, self-cleaning fixture. |
| Queue | `python test_queue.py` | yes | no | `SKIP LOCKED` claiming, lease reclaim, backoff retries, stats. |
| Knowledge ingestion | `python test_knowledge_ingestion.py` | yes | no | Loader, chunker, idempotent re-ingest, pgvector cosine retrieval. |
| Classification | `python test_classification.py` | no | no | Schemas, model registry, provider wiring, refusal without a key. |
| Database | `python test_db.py` | yes | no | Async persistence round trip for a ticket and its messages. |
| Graph | `python test_graph.py` | yes | yes | End-to-end smoke test: create a ticket, run the graph, assert, delete. |

CI (`.github/workflows/security.yml`) runs on pushes to `main`, on pull requests, and on demand. It
installs `backend/requirements.txt` on Python 3.14 and runs `python test_prompt_safety.py --offline`,
which needs no database or API key and fails the build on regression. The offline suite currently
reports 156 checks.

The frontend has no test runner; it is checked by `tsc -b` and oxlint only.

## Project structure

```
backend/      FastAPI app, LangGraph pipeline, guardrails, queue, scripts, tests
frontend/     React agent console
infra/        docker-compose (Postgres 16 with pgvector)
knowledge/    Source documents for retrieval (policies/ and support/)
docs/         Architecture, security, and knowledge-base notes
```

The full layout is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#project-layout).

## Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Pipeline, routing, guardrails, prompt boundary, outbound path, data model, queue, design decisions, build history |
| [docs/SECURITY.md](docs/SECURITY.md) | Security model, what is and is not covered, how to report a vulnerability |
| [docs/knowledge-base.md](docs/knowledge-base.md) | How documents are ingested and re-indexed |

## Security

Customer text is treated as untrusted input. See [docs/SECURITY.md](docs/SECURITY.md) for the security
model, current gaps, and how to report a vulnerability.
