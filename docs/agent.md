# Agent Instructions — ResolveAI

This file is the standing context for any coding agent working on this repo. Read it first, every session, before touching code.

## What this project is

ResolveAI is an AI customer service automation platform: it classifies incoming tickets, retrieves relevant knowledge, routes by confidence (auto-resolve / draft-for-review / escalate), executes guardrailed actions, and learns from agent corrections. Full architecture, data model, and rationale live in `docs/system_design_doc.md` — read it before making any structural change.

## The three docs that govern this build

| Doc | What it governs | When to consult it |
|---|---|---|
| `docs/system_design_doc.md` | Architecture, components, data model, tech stack, guardrail rules | Before adding/changing any backend component, table, or the LLM/LangGraph layer |
| `docs/ROADMAP.md` | What to build, in what order, and what "done" means per phase | At the start of every work session — confirm which phase is active before writing code |
| `docs/design.md` | Colors, type, component patterns for the frontend | Before writing or reviewing any frontend/UI code |

If a request conflicts with one of these docs, flag the conflict explicitly rather than silently picking one side. Don't guess at intent on architecture or guardrail questions — ask.

## How to work through the roadmap

- Work phases in order. Do not start Phase N+1 until Phase N's checklist in `ROADMAP.md` is fully checked off.
- At the start of a session, state which phase you believe is active and what remains before moving on. If unsure, check the repo state against the phase checklists rather than assuming.
- A phase is "done" only when its explicit checklist items are met — not when it "seems to work." If a checklist item can't be verified, say so rather than checking it off.
- Resist building ahead. Polishing the dashboard UI before Phase 5's routing logic is real, or adding multi-channel support before Phase 1's single channel is solid, is scope creep — call it out if asked to do it early, don't just comply silently.

## Non-negotiable guardrails (from `system_design_doc.md` §6)

These apply regardless of which phase is active:
- Dollar/scope caps on any irreversible action (refunds, cancellations, account changes) are enforced **in code**, never only in a prompt.
- Every autonomous action writes an `audit_log` entry *before* it executes, not after.
- Only allow-listed tools/actions are ever bound to the model — no dynamically constructed or arbitrary API calls.
- If confidence is low or a guardrail would be violated, the system must route to a human, never guess or silently proceed.
- Never weaken a guardrail to make a demo look more impressive. If asked to, push back and explain why.

## Tech stack conventions

- **LLM orchestration:** LangGraph `StateGraph` is the decision engine (see `system_design_doc.md` §3.5). Confidence routing is expressed as conditional edges, not if/else chains in application code.
- **Model calls:** always via LangChain's `init_chat_model` + the task→provider/model config registry — never call a provider SDK directly. New task types get a config entry, not a hardcoded model string.
- **Fallbacks:** any production-path model call should have `.with_fallbacks([...])` configured, not just a bare call.
- **Data:** Postgres + pgvector. Schema changes go through Alembic migrations, never manual `ALTER TABLE`.
- **Frontend:** React + Tailwind, following `design.md` exactly — see below.

## Frontend rules (non-negotiable, not stylistic preference)

- Follow `design.md`'s color tokens and component patterns exactly. Do not introduce new colors, shadows, filled status badges, or typefaces without updating `design.md` first and explaining why.
- Status is shown via the 3px left-border pattern, never a filled pill.
- No gradients, no card-shadow kit, no ALL-CAPS labels, no arrow-suffixed buttons — these are explicitly listed as rejected defaults in `design.md`'s "what not to do" section for a reason; don't reintroduce them because a library's default component looks like that.
- If a UI library's default component conflicts with `design.md` (e.g., a component kit that only ships filled badges), override the styling rather than accepting the default.

## When something is ambiguous

- Prefer asking a short, specific question over guessing on: guardrail thresholds, schema changes, or anything that affects the audit trail.
- For everything else (naming, minor UI spacing, test structure), make a reasonable choice, state the assumption in a comment or commit message, and move on — don't block on small things.

## Definition of done, project-wide

A feature isn't done when it works once in a happy-path demo. It's done when: the relevant `ROADMAP.md` checklist is satisfied, guardrails from `system_design_doc.md` §6 are provably intact (not just assumed), and the UI matches `design.md` rather than a component library's default look.
