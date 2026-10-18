# Security

## Reporting a vulnerability

Please do not open a public issue for security problems. Report them privately to **[SECURITY CONTACT EMAIL]**
(or use GitHub's private vulnerability reporting on the repository, if enabled). Include steps to
reproduce, the affected file or endpoint, and the impact you observed. Expect an acknowledgement within
**[N] days**.

Supported version: the `main` branch only. This is a prototype and has no release branches.

## Scope of this document

ResolveAI's security work so far focuses on **what the AI is allowed to do and what an attacker can make
it do through customer-supplied text**. It does not yet cover access control, deployment hardening, or
multi-user isolation. Both halves are listed below so nobody mistakes one for the other.

## Covered and tested

| Area | What the code does | Where |
|---|---|---|
| Action limits | Allow-list of `refund`, `order_status`, `password_reset`; a hard refund cap (`REFUND_INR_CAP = 2000`) enforced in code. A breach writes `guardrail_violation` and routes to human review. | `backend/app/api/tickets.py` |
| Over-promising | A draft asserting an action that was not taken is downgraded to human review and audited as `unverified_promise_blocked`. | `backend/app/core/promises.py` |
| Prompt injection via hidden content | Hidden HTML, CSS-hidden text, scripts, comments, and invisible characters are removed before the model reads a message. | `backend/app/core/prompt_safety.py` |
| Instruction/data separation | Customer text reaches a prompt only inside fixed fences under a standing "this is data" instruction. Fence-like markers in the text are defanged. | `backend/app/core/prompt_safety.py` |
| Evidence preservation | The raw inbound message is stored verbatim; only kinds of removed content (never the text) are written to the audit log. | `backend/app/core/outbound.py` |
| Outbound formatting | All outbound messages pass one boundary that renders plain text and escapes email HTML. | `backend/app/core/text_format.py`, `backend/app/core/outbound.py` |
| Retrieval scoping | Feedback chunks are scoped to the customer they came from, fail-closed. | `backend/app/graphs/ticket_graph.py` |
| Knowledge poisoning | Agent edits enter retrieval only with an explicit `--approve`. | `backend/feedback_loop.py` |
| Auditability | Decisions and actions are recorded in an append-only audit table, rendered next to the ticket in the console. | `backend/app/core/audit.py` |

Regression coverage: `python test_prompt_safety.py --offline` runs 156 checks with no database and no API
key, and CI runs it on every push to `main` and every pull request
(`.github/workflows/security.yml`).

Details of the prompt boundary and outbound path: see
[ARCHITECTURE.md](ARCHITECTURE.md#untrusted-input-the-prompt-boundary).

## Not covered (known gaps)

| Gap | Impact | Notes |
|---|---|---|
| No authentication or authorization | Any client that can reach the API can approve a draft or trigger a tool action. | Reviews are attributed to a hardcoded `agent_1`, not a real identity. Do not expose the API publicly. |
| Rate limiting is in-process | Limits are per process and reset on restart; they do not hold across multiple instances. | Use a shared store for real deployments. |
| No idempotency key on ticket creation | A retried `POST /tickets` creates a duplicate ticket. | |
| Unused email guardrails | `EMAIL_MAX_SIZE` and `EMAIL_REQUIRED_FIELDS` are declared but not enforced, so oversized or incomplete payloads are not rejected by those checks. | `backend/app/api/tickets.py` |
| Simulated actions and email | The refund, order, and password-reset tools do not touch real systems; no email is sent. | Real integrations will need their own credential handling, scoping, and review. |
| PII handling not documented | The README does not describe redaction of personal data before text reaches a model provider. | Confirm in the code, then document the result here. Review your provider's data-handling terms before using real customer data. |
| No deployment hardening | No container image, TLS configuration, secrets manager, or hosting manifest. | |
| No model-quality evaluation | Classification accuracy and confidence calibration have not been measured. | The security suite checks code properties, not model behavior. |

## Secrets

Provider keys and `DATABASE_URL` are read from a repository-root `.env`, which should never be committed.
Use `.env.example` as the template. The defaults in `backend/app/core/config.py` include a local
development database password; replace it for any non-local setup.
