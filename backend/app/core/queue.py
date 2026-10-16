"""Postgres-backed work queue for ticket processing.

Processing a ticket is an LLM round trip, so it cannot happen inside the request
that creates the ticket without holding that request open for seconds. Instead
the API inserts a row into ``ticket_jobs`` and a worker claims it:

    UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)

``SKIP LOCKED`` is what makes this a queue rather than a table with a lock
contention problem — several workers can drain the same table at once and each
gets a different row, with no coordination and no extra infrastructure.

A job claimed by a worker that then dies would sit in ``running`` forever, so a
claim also reclaims rows whose lease has expired.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SyncSessionLocal
from app.graphs.runner import apply_graph_result, run_ticket_graph
from app.models.base import JobStatus, Ticket, TicketJob

logger = logging.getLogger(__name__)

# Identifies this process in the claimed_by column, so a stuck job can be traced
# back to the worker that took it.
WORKER_ID = f"worker-{uuid4().hex[:8]}"

# One statement, so the lock is taken and the row handed over atomically: the
# subquery locks a single claimable row and the outer UPDATE moves it to running.
# A second worker running this at the same time skips the locked row and takes
# the next one.
_CLAIM_SQL = text("""
    UPDATE ticket_jobs
       SET status = 'running',
           attempts = attempts + 1,
           claimed_at = now(),
           claimed_by = :worker_id,
           updated_at = now()
     WHERE id = (
         SELECT id
           FROM ticket_jobs
          WHERE (status = 'pending' AND available_at <= now())
             OR (status = 'running'
                 AND claimed_at < now() - (CAST(:lease_seconds AS integer) * INTERVAL '1 second'))
          ORDER BY available_at, created_at
          FOR UPDATE SKIP LOCKED
          LIMIT 1
     )
    RETURNING id, ticket_id, kind, attempts, max_attempts
""")


async def enqueue_ticket_job(db: AsyncSession, ticket_id: UUID, kind: str = "process") -> None:
    """Queue a graph run for a ticket, inside the caller's transaction.

    Sharing the caller's transaction matters: the ticket and its job are
    committed together, so a ticket can never exist without the job that will
    process it.
    """
    db.add(
        TicketJob(
            id=uuid4(),
            ticket_id=ticket_id,
            kind=kind,
            max_attempts=settings.JOB_MAX_ATTEMPTS,
        )
    )


def claim_next_job(worker_id: str = WORKER_ID) -> dict | None:
    """Take the oldest claimable job, or return None when the queue is idle."""
    with SyncSessionLocal() as db:
        row = db.execute(
            _CLAIM_SQL,
            {"worker_id": worker_id, "lease_seconds": settings.JOB_LEASE_SECONDS},
        ).mappings().first()
        db.commit()
        return dict(row) if row else None


def complete_job(job_id: UUID) -> None:
    with SyncSessionLocal() as db:
        db.execute(
            text(
                "UPDATE ticket_jobs"
                "   SET status = :status, last_error = NULL, updated_at = now()"
                " WHERE id = :job_id"
            ),
            {"job_id": job_id, "status": JobStatus.DONE.value},
        )
        db.commit()


def fail_job(job_id: UUID, error: str, attempts: int, max_attempts: int) -> None:
    """Requeue with a growing backoff, or give up once attempts are exhausted.

    The job is never deleted: a failed job is the record that a ticket was left
    unprocessed, and the health endpoint reports how many there are.
    """
    exhausted = attempts >= max_attempts
    status_value = JobStatus.FAILED.value if exhausted else JobStatus.PENDING.value
    backoff_seconds = 0 if exhausted else min(30, 2 ** attempts)

    with SyncSessionLocal() as db:
        db.execute(
            text("""
                UPDATE ticket_jobs
                   SET status = :status,
                       last_error = :error,
                       available_at = now() + (CAST(:backoff AS integer) * INTERVAL '1 second'),
                       claimed_at = NULL,
                       updated_at = now()
                 WHERE id = :job_id
            """),
            {
                "job_id": job_id,
                "status": status_value,
                "error": error[:2000],
                "backoff": backoff_seconds,
            },
        )
        db.commit()


def run_job(job: dict) -> None:
    """Run one claimed job, writing the graph outcome onto the ticket."""
    with SyncSessionLocal() as db:
        ticket = db.get(Ticket, job["ticket_id"])
        if ticket is None:
            # The ticket was deleted (or its customer's data was purged) while
            # the job waited. Nothing to process.
            logger.warning("ticket job %s: ticket %s is gone", job["id"], job["ticket_id"])
            return
        result = run_ticket_graph(ticket)
        apply_graph_result(ticket, result)
        db.commit()


_worker_thread: threading.Thread | None = None
_worker_stop = threading.Event()


def worker_loop(stop: threading.Event) -> None:
    """Drain the queue until asked to stop.

    Sequential on purpose: the graph is CPU- and IO-bound around a shared
    database connection, so one job at a time keeps the failure modes simple.
    To go faster, start more processes — the claim is already safe for that.
    """
    logger.info("ticket worker %s started", WORKER_ID)
    while not stop.is_set():
        try:
            job = claim_next_job()
        except Exception:
            logger.exception("ticket worker: could not claim a job")
            stop.wait(settings.WORKER_POLL_SECONDS)
            continue

        if job is None:
            stop.wait(settings.WORKER_POLL_SECONDS)
            continue

        try:
            run_job(job)
        except Exception as exc:
            # Recording the failure must not itself take the worker down.
            logger.exception("ticket job %s failed", job["id"])
            try:
                fail_job(job["id"], str(exc), job["attempts"], job["max_attempts"])
            except Exception:
                logger.exception("ticket worker: could not record the failure of job %s", job["id"])
        else:
            complete_job(job["id"])

    logger.info("ticket worker %s stopped", WORKER_ID)


def start_worker() -> None:
    global _worker_thread
    if not settings.WORKER_ENABLED:
        logger.info("ticket worker disabled by configuration")
        return
    _worker_stop.clear()
    _worker_thread = threading.Thread(
        target=worker_loop, args=(_worker_stop,), name="ticket-worker", daemon=True
    )
    _worker_thread.start()


def stop_worker() -> None:
    global _worker_thread
    if _worker_thread is None:
        return
    _worker_stop.set()
    _worker_thread.join(timeout=5)
    _worker_thread = None


def worker_running() -> bool:
    return _worker_thread is not None and _worker_thread.is_alive()


def queue_stats() -> dict:
    """Queue depth, for the health endpoint.

    A growing pending count or any failed job means tickets are not being
    processed — the thing worth alerting on.
    """
    with SyncSessionLocal() as db:
        rows = db.execute(
            text("SELECT status, count(*) AS total FROM ticket_jobs GROUP BY status")
        ).mappings().all()
        oldest_pending = db.execute(
            text("SELECT min(available_at) FROM ticket_jobs WHERE status = :status"),
            {"status": JobStatus.PENDING.value},
        ).scalar()

    counts = {row["status"]: row["total"] for row in rows}
    oldest_age = None
    if oldest_pending is not None:
        oldest_age = round((datetime.now(timezone.utc) - oldest_pending).total_seconds(), 1)

    return {
        "ok": True,
        "worker_running": worker_running(),
        "pending": counts.get(JobStatus.PENDING.value, 0),
        "running": counts.get(JobStatus.RUNNING.value, 0),
        "failed": counts.get(JobStatus.FAILED.value, 0),
        "oldest_pending_seconds": oldest_age,
    }
