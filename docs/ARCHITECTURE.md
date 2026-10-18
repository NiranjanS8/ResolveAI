# Architecture

How ResolveAI works internally. For setup and usage, see the [README](../README.md).

## Contents

- [System overview](#system-overview)
- [The ticket pipeline](#the-ticket-pipeline)
- [Routing: how a decision is made](#routing-how-a-decision-is-made)
- [Human in the loop](#human-in-the-loop)
- [Guardrails enforced in code](#guardrails-enforced-in-code)
- [Untrusted input: the prompt boundary](#untrusted-input-the-prompt-boundary)
- [Outbound: one send boundary](#outbound-one-send-boundary)
- [Cost and observability](#cost-and-observability)
- [Data model](#data-model)
- [The job queue](#the-job-queue)
- [Design decisions](#design-decisions)
- [Project layout](#project-layout)
- [Appendix: build history](#appendix-build-history)

## System overview

```mermaid
flowchart TD
    UI[React agent console :5173]
    DB[(Postgres + pgvector)]
    PC[(provider_calls)]
    LLM[LLM providers]

    subgraph API[FastAPI :8000]
        TK[tickets API]
        AN[analytics API]
        HE[health API]
        WK[queue worker]
        RUN[graphs/runner.py]
        JOB[(ticket_jobs)]
    end

    subgraph G[LangGraph ticket graph]
        C[classify]
        R[retrieve]
        D[decide]
        AR[auto_resolve]
        DR[draft_for_review]
        ES[escalate]
    end

    OB[send_customer_message]

    UI -->|REST| TK
    TK -->|enqueue| JOB
    JOB --> WK
    WK --> RUN
    RUN --> C
    C --> R
    R --> D
    D -->|score >= high| AR
    D -->|score >= medium| DR
    D -->|otherwise| ES
    C --> LLM
    D --> LLM
    LLM --> PC
    AR --> OB
    DR --> OB
    OB --> DB
    DR -.->|interrupt| UI
    UI -.->|approve / edit / reject| TK
    TK --> DB
    AN --> DB
    HE --> DB
    JOB --> DB
```

Request path: `POST /api/v1/tickets` writes the ticket and a job in one transaction and returns
immediately. The worker claims the job, runs the graph, and copies the resulting state back onto the
ticket row.

## The ticket pipeline

`backend/app/graphs/ticket_graph.py` wires six nodes:

| Node | What it does |
|---|---|
| `classify` | One structured LLM call for intent, urgency, sentiment, and confidence. Returns a validated `ClassificationOutput`, and asks for honesty: vague tickets must score below 0.70, because that number decides who answers the customer. |
| `retrieve` | Embeds the ticket, then runs a pgvector cosine search over `knowledge_chunks` for the top 5 chunks. Feedback chunks are scoped to the customer they came from, fail-closed. |
| `decide` | Computes the routing score, reads the per-intent thresholds, drafts the reply, and picks the branch. This is where an unverified promise downgrades an auto-resolve. |
| `auto_resolve` | Sends the reply through the outbound boundary and writes an `auto_resolved` audit row carrying the intent, classifier certainty, retrieval relevance, and final score. |
| `draft_for_review` | Calls `interrupt()` and waits for a human, persisted by the checkpointer. Resume with `approve`, `edit`, or `reject`. |
| `escalate` | Writes an `escalated` audit row with the reason, so the escalation breakdown in analytics is real data rather than a guess. |

## Routing: how a decision is made

```
relevance     = max(similarity of retrieved chunks)     # 0.0 when nothing was retrieved
routing_score = classifier_confidence * relevance
```

| Decision | Condition |
|---|---|
| `auto_resolve` | `routing_score >= high` |
| `draft_for_review` | `routing_score >= medium` |
| `escalate` | otherwise, including when no chunk was retrieved |

The second term keeps this honest. A confident classifier with no matching policy scores zero and
escalates, so the agent never answers from its own imagination about company policy.

Per-intent thresholds (`backend/app/core/thresholds.py`):

| Intent | high | medium |
|---|---|---|
| refund | 0.70 | 0.50 |
| technical | 0.80 | 0.60 |
| billing | 0.75 | 0.55 |
| account | 0.70 | 0.50 |
| order_status | 0.65 | 0.45 |
| password_reset | 0.65 | 0.45 |
| cancellation | 0.70 | 0.50 |
| general | 0.60 | 0.40 |

One further gate sits after the score: a draft that asserts an action has been or will be taken fails
`find_unverified_promises` and is downgraded to `draft_for_review` with an `unverified_promise_blocked`
audit row. The promise families are refund, cancellation, password reset, account change, compensation,
human escalation, and completed actions (`backend/app/core/promises.py`).

## Human in the loop

A paused run is resumed through the API, and the reviewer's decision is recorded:

| Endpoint | Effect |
|---|---|
| `POST /tickets/{id}/approve` | Sends the draft as-is; writes `agent_feedback` and a `draft_approved` audit row. |
| `POST /tickets/{id}/edit` | Sends the edited text; writes `agent_feedback` (original and edited) and `draft_edited`. |
| `POST /tickets/{id}/reject` | Discards the draft and escalates; writes `agent_feedback` and `draft_rejected`. |

All three require the ticket to be in `draft_for_review` and return `409` otherwise. The `agent_feedback`
rows are what the draft-acceptance metric and the feedback loop read.

## Guardrails enforced in code

| Guardrail | Value | Behaviour |
|---|---|---|
| Action allow-list | `refund`, `order_status`, `password_reset` | Anything else raises `400`. |
| Refund cap | `REFUND_INR_CAP = 2000` | A breach writes `guardrail_violation` and routes to human review instead of executing. |
| Channels | `email`, `chat` | Anything else is rejected at creation. |
| Rate limit | 60 requests / 60 seconds per customer | Sliding window, in-process. |
| Unverified promises | 7 families | Auto-resolve drafts matching one are downgraded to review. |
| Untrusted input | hidden content and injection | Neutralized at the prompt boundary and audited. |
| Outbound format | plain text | Converted at one boundary; conversions counted as `format_sanitized`. |

The allow-list and cap live in `backend/app/api/tickets.py` (`ACTIONS_ALLOWED`, `REFUND_INR_CAP`).

## Untrusted input: the prompt boundary

The customer writes the subject and body, and inbound email can carry arbitrary HTML. So untrusted text
never reaches a prompt by interpolation. `backend/app/core/prompt_safety.py` provides:

- **Fencing.** Untrusted values arrive inside `<<<BEGIN-UNTRUSTED-DATA:label>>>` /
  `<<<END-UNTRUSTED-DATA:label>>>`, plus a standing instruction that anything inside a fence is data,
  never an instruction.
- **Neutralization.** Content an ordinary reader cannot see is removed before the model reads it: the
  `hidden` attribute, inline styles that hide text (`display:none`, `visibility:hidden`, zero opacity,
  zero font size, white or transparent text with no dark background in scope, text pushed out of its
  box, a zero-size clipped box), `<style>` rules with simple selectors including `!important`, `<script>`
  bodies, HTML comments, and invisible or control characters. A removed element is replaced with
  `[hidden content removed]`, so the message still reads as a sentence and the model knows something was
  there. Ancestor backgrounds are tracked so legitimate white-on-dark header text survives. Purely
  structural plumbing (`<head>`, `<noscript>`, `<template>`) is dropped silently, because an ordinary
  email should not look like it withheld something.
- **Defanging.** Anything shaped like a section marker inside untrusted text has its `<<<` rewritten to a
  full-width equivalent, so a message cannot close its own fence.
- **Evidence and audit.** The stored inbound message is untouched. The neutralizer returns what it
  removed by kind, and the graph writes an `untrusted_content_neutralized` audit row (kinds only, never
  the text). The console shows the reviewer which kinds of content were withheld on that message.

The message builders (`build_classify_messages`, `build_draft_messages`) are separate from the nodes, so
the instruction/data boundary is a pure function that can be asserted without calling a model. That is
how the security suite runs in CI with no database and no API key.

## Outbound: one send boundary

`send_customer_message(ticket_id, body, ...)` is the only way an agent, AI, or system message enters a
customer's thread. It reads the ticket's channel itself, so a caller cannot choose one, then:

1. Parses the body with markdown-it and renders plain text: emphasis and code markers dropped, links
   become `text (url)`, lists keep their prefixes, tables flatten, blank-line runs collapse.
2. For the email channel, escapes the text and wraps it as simple HTML paragraphs.
3. Writes a `format_sanitized` audit row and an internal counter row when it had to remove markup, so a
   model drifting into Markdown is visible rather than silent.
4. Inserts the `ticket_messages` row with `content` set to the exact plain text.

Inbound `customer` messages are the deliberate exception: they are stored verbatim, unsanitized, as
evidence. Code: `backend/app/core/outbound.py`, `backend/app/core/text_format.py`.

## Cost and observability

Every LLM and embedding call is recorded in `provider_calls` with provider, model, task, tokens, latency,
success, and cost. `backend/app/core/pricing.py` holds a dated price table
(`PRICE_SNAPSHOT_DATE = "2026-10"`) and computes
`(input_tokens * input_price + output_tokens * output_price) / 1_000_000`. A model without a published
price stores no cost and is reported as an unpriced call rather than as zero.

`backend/app/core/metrics.py` is the single source of truth for the analytics the API and the console
show: volume and deflection rate, time to first reply (average, median, p95), cost and cost per ticket,
provider health by task, draft review outcomes, escalation reasons, guardrail interceptions, and the
deflection trend. `backend/analytics_dashboard.py` prints the same snapshot on the command line.
Analytics default to a 30-day window, and a metric with an empty sample reports `null` rather than zero.

## Data model

| Table | Holds |
|---|---|
| `tickets` | The ticket, its classification, the routing artifacts (`confidence`, `retrieved_context`), the draft, channel, and status. |
| `ticket_messages` | The customer thread. Inbound rows verbatim; outbound rows plain text with a `meta` block (channel, source, prompt version, whether it was sanitized). |
| `audit_log` | Append-only record of decisions and actions with a JSON payload: auto-resolve inputs, escalation reasons, guardrail violations, sanitization events, neutralized content. |
| `knowledge_chunks` | Indexed knowledge with a pgvector embedding, source type, document title, path, chunk index, and content hash. |
| `agent_feedback` | Original draft, edited response, agent id. Feeds draft acceptance and the feedback loop. |
| `ticket_jobs` | The processing queue. |
| `provider_calls` | One row per model call: tokens, latency, cost, success, error. |

Statuses: `new`, `classifying`, `retrieving`, `deciding`, `auto_resolved`, `draft_for_review`,
`escalated`, `resolved`. Migrations live in `backend/alembic/versions/`: `0001` schema, `0002` channel and
drafts, `0003` pgvector and document metadata, `0004` the job queue.

## The job queue

Ticket creation must not wait on a model, so it enqueues a row and returns. A worker claims one job with
a single `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)`, which is why no broker is
needed: Postgres already provides atomic claiming without blocking competing workers.

- A job is claimable when it is `pending` and due, or `running` past its lease (`JOB_LEASE_SECONDS`,
  default 300), which is how a worker that died mid-job gets recovered.
- Failures retry with exponential backoff (`min(30, 2 ** attempts)` seconds) up to `JOB_MAX_ATTEMPTS`
  (default 3), then land in `failed` with the error stored.
- Statuses are `pending`, `running`, `done`, `failed`. `queue_stats()` is reported by the health
  endpoint, and a backlog is informational, not fatal.

Code: `backend/app/core/queue.py`.

## Design decisions

| Decision | Why | Where |
|---|---|---|
| Postgres `SKIP LOCKED` queue instead of Redis or Celery | Ticket processing calls an LLM, so it must not block the request. Claiming with `FOR UPDATE SKIP LOCKED` gives at-least-once delivery with retries, backoff, and a lease for dead workers, with no extra broker to run or explain. | `backend/app/core/queue.py` |
| The worker runs inside the API process | Fewer moving parts for a single-node deployment; `WORKER_ENABLED=false` splits it into a separate drainer when you want one. | `backend/app/main.py`, `backend/app/core/queue.py` |
| Human review is a LangGraph `interrupt()`, not a status flag | The run genuinely pauses and is persisted by the Postgres checkpointer, so a restart does not lose a pending review, and the graph owns the pause instead of the HTTP layer. | `backend/app/graphs/ticket_graph.py`, `backend/app/graphs/runner.py` |
| Raw inbound content is stored verbatim | The neutralized text is not what you want in an incident review. Evidence stays untouched; neutralization happens at the prompt boundary. | `backend/app/core/outbound.py`, `backend/app/core/prompt_safety.py` |
| Plain text only, sanitized at send | What the reviewer approves is byte-for-byte what is sent. Markdown becomes plain text at one boundary, and any conversion is counted so markup drift is visible instead of silent. | `backend/app/core/text_format.py`, `backend/app/core/outbound.py` |
| Deterministic fences with no random nonce | A per-request nonce would make every prompt prefix different and defeat prompt caching. Fences are fixed and tested instead. | `backend/app/core/prompt_safety.py` |
| Graph plumbing shared by the API and the worker | Both sides must start, resume, and record a run identically or they drift. That logic lives in one module. | `backend/app/graphs/runner.py` |
| Agent feedback enters retrieval only with explicit approval | A wrong correction silently entering the knowledge base is a permanent, invisible regression. `feedback_loop.py` lists candidates and indexes nothing without `--approve`, embedding the edited response rather than the original draft. | `backend/feedback_loop.py` |
| Analytics read live tables | No precomputed dashboard numbers that can drift from reality; the range query recomputes from tickets, provider calls, audit rows, and reviews. | `backend/app/core/metrics.py`, `backend/app/api/analytics.py` |

## Project layout

```
backend/
  app/
    api/          tickets, analytics, health, deps
    core/         config, llm, providers, model_registry, pricing, metrics,
                  queue, outbound, text_format, prompt_safety, promises,
                  thresholds, knowledge, embeddings, audit
    graphs/       state, ticket_graph (nodes and prompts), runner (start/resume)
    models/       SQLAlchemy tables and enums
    schemas/      request/response and structured LLM output contracts
    db/           engine and session
  alembic/        alembic.ini + versions/
  run.py                  start the API and the worker
  ingest_knowledge.py     (re)index knowledge/ into knowledge_chunks
  seed_tickets.py         replay curated demo tickets through the real graph
  analytics_dashboard.py  print the analytics snapshot
  feedback_loop.py        review agent edits and promote approved ones
  test_*.py               the test suites
frontend/
  src/
    api/tickets.ts        typed fetch client for every endpoint
    lib/ticketDisplay.ts  the single rendering contract (labels, thresholds, scores)
    pages/HomePage.tsx    state, polling, and every action handler
    components/           Navbar, TicketList, TicketDetailPane, DraftCard,
                          ActionButtons, TicketForm, AnalyticsDashboardView,
                          AnalyticsChart, Icon, Toast
    index.css             design tokens, light and dark
  vite.config.ts          dev server on 5173, proxies /api to 8000
docs/
  ARCHITECTURE.md         this document
  SECURITY.md             security model and reporting
  knowledge-base.md       how documents are ingested and re-indexed
infra/
  docker-compose.yml      Postgres 16 with pgvector
knowledge/                the source documents, split into policies/ and support/
```

## Appendix: build history

The commit history is the roadmap, one working slice at a time.

| Phase | What landed |
|---|---|
| Scaffolding | Repository structure, docker-compose with Postgres and pgvector, FastAPI and React booting, Alembic, health check. |
| Ingestion | `POST`/`GET` tickets plus the console form and queue list. |
| Graph skeleton | `TicketState`, stub nodes, the Postgres checkpointer, ticket to graph wiring. |
| Classification | Real LLM classification with a fallback model and a `provider_calls` row per call. |
| Retrieval | `ingest_knowledge.py`, chunking with content hashes, pgvector top-k search. |
| Decision engine | The confidence times relevance score, per-intent thresholds, and the three branches. |
| Drafts and review | Plain-text drafting, the review interrupt, approve/edit/reject, and agent feedback. |
| Actions | Allow-listed refund, order status, and password reset, with the refund cap in code. |
| Analytics | The metrics module, the range API, and the console dashboard. |
| Queue | The Postgres job queue with `SKIP LOCKED`, leases, retries, and in-process worker. |
| Operations | Health reporting per dependency, `503` on a broken database, structured logging. |
| Security work | The prompt boundary and neutralizer, the promise guard, customer-scoped feedback retrieval, the hidden-content warning, and the offline regression suite in CI. |
