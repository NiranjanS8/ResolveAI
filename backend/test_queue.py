"""Behaviour of the Postgres-backed ticket queue.

The queue's whole justification is the claim: it must hand each job to exactly
one worker, skip rows another worker is holding, respect a backoff, and reclaim a
job whose worker died. Those are the properties asserted here.

The tests are self-cleaning and do not start the worker. run_job is the only part
that calls the LLM, so it is exercised only on its "ticket is gone" path.
"""
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.core.queue import (
    claim_next_job,
    complete_job,
    enqueue_ticket_job,
    fail_job,
    queue_stats,
    run_job,
    worker_running,
)
from app.db.session import AsyncSessionLocal, SyncSessionLocal
from app.models.base import JobStatus, Ticket, TicketJob

TEST_CUSTOMER_ID = "cust_queue_test"

CHECKS = 0
FAILURES: list[str] = []


def expect(label: str, actual, expected) -> None:
    global CHECKS
    CHECKS += 1
    if actual != expected:
        FAILURES.append(f"{label}: expected {expected!r}, got {actual!r}")


def count_claimable(exclude_ticket: UUID | None = None) -> int:
    """Claimable jobs, optionally excluding the fixture's own ticket.

    The claim is deliberately global, so a job left pending by the running app
    would be picked ahead of the fixture's and make these assertions meaningless.
    """
    conditions = [
        TicketJob.status == JobStatus.PENDING.value,
        TicketJob.available_at <= datetime.now(timezone.utc),
    ]
    if exclude_ticket is not None:
        conditions.append(TicketJob.ticket_id != exclude_ticket)

    with SyncSessionLocal() as db:
        return db.execute(select(func.count()).select_from(TicketJob).where(*conditions)).scalar()


def create_test_ticket() -> UUID:
    with SyncSessionLocal() as db:
        ticket = Ticket(
            id=uuid4(),
            customer_id=TEST_CUSTOMER_ID,
            subject="queue fixture",
            body="fixture",
            channel="chat",
        )
        db.add(ticket)
        db.commit()
        return ticket.id


def clear_jobs(ticket_id: UUID) -> None:
    with SyncSessionLocal() as db:
        db.execute(delete(TicketJob).where(TicketJob.ticket_id == ticket_id))
        db.commit()


def add_job(
    ticket_id: UUID,
    status: JobStatus = JobStatus.PENDING,
    available_at: datetime | None = None,
    claimed_at: datetime | None = None,
    attempts: int = 0,
    max_attempts: int = 3,
    kind: str = "process",
) -> UUID:
    job_id = uuid4()
    with SyncSessionLocal() as db:
        db.add(
            TicketJob(
                id=job_id,
                ticket_id=ticket_id,
                kind=kind,
                status=status,
                attempts=attempts,
                max_attempts=max_attempts,
                available_at=available_at or datetime.now(timezone.utc),
                claimed_at=claimed_at,
            )
        )
        db.commit()
    return job_id


def read_job(job_id: UUID) -> dict:
    with SyncSessionLocal() as db:
        job = db.get(TicketJob, job_id)
        return {
            "status": job.status,
            "attempts": job.attempts,
            "claimed_by": job.claimed_by,
            "claimed_at": job.claimed_at,
            "available_at": job.available_at,
            "last_error": job.last_error,
        }


def test_claim_takes_the_oldest_ready_job(ticket_id: UUID, worker: str) -> None:
    clear_jobs(ticket_id)
    now = datetime.now(timezone.utc)
    older = add_job(ticket_id, available_at=now - timedelta(minutes=2))
    newer = add_job(ticket_id, available_at=now - timedelta(minutes=1))

    first = claim_next_job(worker)
    expect("the oldest ready job is claimed first", first["id"], older)
    expect("a claimed job is running", read_job(older)["status"], JobStatus.RUNNING)
    expect("a claim counts as an attempt", read_job(older)["attempts"], 1)
    expect("a claim records who took it", read_job(older)["claimed_by"], worker)
    expect("a claim records when it was taken", read_job(older)["claimed_at"] is not None, True)

    second = claim_next_job(worker)
    expect("the next claim takes the next job", second["id"], newer)

    expect("an empty queue yields no job", claim_next_job(worker), None)


def test_claim_skips_a_job_that_is_backing_off(ticket_id: UUID, worker: str) -> None:
    clear_jobs(ticket_id)
    add_job(ticket_id, available_at=datetime.now(timezone.utc) + timedelta(hours=1))

    expect("a job still backing off is not claimable", claim_next_job(worker), None)


def test_claim_leaves_a_live_claim_alone(ticket_id: UUID, worker: str) -> None:
    clear_jobs(ticket_id)
    add_job(ticket_id, status=JobStatus.RUNNING, attempts=1, claimed_at=datetime.now(timezone.utc))

    expect("a job another worker is still running is not stolen", claim_next_job(worker), None)


def test_claim_reclaims_a_job_whose_worker_died(ticket_id: UUID, worker: str) -> None:
    clear_jobs(ticket_id)
    expired = datetime.now(timezone.utc) - timedelta(seconds=settings.JOB_LEASE_SECONDS + 60)
    job_id = add_job(ticket_id, status=JobStatus.RUNNING, attempts=1, claimed_at=expired)

    reclaimed = claim_next_job(worker)
    expect("a job past its lease is reclaimed", reclaimed["id"], job_id)
    expect("reclaiming counts as another attempt", read_job(job_id)["attempts"], 2)
    expect("reclaiming records the new owner", read_job(job_id)["claimed_by"], worker)


def test_concurrent_workers_never_share_a_job(ticket_id: UUID) -> None:
    clear_jobs(ticket_id)
    queued = {add_job(ticket_id) for _ in range(6)}
    taken: list[UUID] = []
    lock = threading.Lock()

    def drain(worker: str) -> None:
        while True:
            job = claim_next_job(worker)
            if job is None or job["ticket_id"] != ticket_id:
                return
            with lock:
                taken.append(job["id"])

    threads = [threading.Thread(target=drain, args=(f"test-worker-{index}",)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    expect("two workers drain every queued job", len(taken), 6)
    expect("no job is handed to two workers", len(set(taken)), 6)
    expect("only the fixture's jobs were taken", set(taken), queued)


def test_complete_marks_a_job_done(ticket_id: UUID, worker: str) -> None:
    clear_jobs(ticket_id)
    job_id = add_job(ticket_id)
    claim_next_job(worker)

    complete_job(job_id)
    expect("a completed job is done", read_job(job_id)["status"], JobStatus.DONE)
    expect("a completed job carries no error", read_job(job_id)["last_error"], None)


def test_fail_retries_with_backoff_then_gives_up(ticket_id: UUID) -> None:
    clear_jobs(ticket_id)
    job_id = add_job(ticket_id, max_attempts=3)

    before = datetime.now(timezone.utc)
    fail_job(job_id, "provider timed out", attempts=1, max_attempts=3)
    retry = read_job(job_id)
    expect("a retryable failure goes back to pending", retry["status"], JobStatus.PENDING)
    expect("a retryable failure records the reason", retry["last_error"], "provider timed out")
    expect("a retry is pushed into the future", retry["available_at"] > before, True)
    expect("a retry releases the claim", retry["claimed_at"], None)

    fail_job(job_id, "provider timed out", attempts=3, max_attempts=3)
    expect("an exhausted job is marked failed", read_job(job_id)["status"], JobStatus.FAILED)


def test_run_job_survives_a_deleted_ticket(missing_ticket: UUID) -> None:
    job = {
        "id": uuid4(),
        "ticket_id": missing_ticket,
        "kind": "process",
        "attempts": 1,
        "max_attempts": 3,
    }

    try:
        run_job(job)
        raised = None
    except Exception as exc:
        raised = repr(exc)

    expect("a job for a deleted ticket is dropped quietly", raised, None)


def test_enqueue_shares_the_callers_transaction(ticket_id: UUID) -> None:
    clear_jobs(ticket_id)

    async def enqueue_and_inspect_uncommitted() -> int:
        async with AsyncSessionLocal() as db:
            await enqueue_ticket_job(db, ticket_id, kind="reprocess")
            # A second connection cannot see the row until this session commits.
            with SyncSessionLocal() as other_connection:
                visible = other_connection.execute(
                    select(func.count())
                    .select_from(TicketJob)
                    .where(TicketJob.ticket_id == ticket_id)
                ).scalar()
            await db.commit()
            return visible

    visible_before_commit = asyncio.run(enqueue_and_inspect_uncommitted())
    expect("a job is invisible until its caller commits", visible_before_commit, 0)

    with SyncSessionLocal() as db:
        job = db.execute(select(TicketJob).where(TicketJob.ticket_id == ticket_id)).scalar_one()
        expect("a committed job is pending", job.status, JobStatus.PENDING)
        expect("a committed job uses the configured attempt budget", job.max_attempts, settings.JOB_MAX_ATTEMPTS)
        expect("the enqueued kind is recorded", job.kind, "reprocess")


def test_queue_stats_tracks_depth(ticket_id: UUID) -> None:
    clear_jobs(ticket_id)
    before = queue_stats()

    add_job(ticket_id)
    add_job(ticket_id)
    add_job(ticket_id, status=JobStatus.RUNNING, attempts=1, claimed_at=datetime.now(timezone.utc))
    add_job(ticket_id, status=JobStatus.FAILED, attempts=3)

    after = queue_stats()
    expect("pending depth grows by the queued jobs", after["pending"] - before["pending"], 2)
    expect("running depth grows by the running job", after["running"] - before["running"], 1)
    expect("failed depth grows by the failed job", after["failed"] - before["failed"], 1)
    expect("the oldest pending job's age is reported", after["oldest_pending_seconds"] is not None, True)
    expect("no worker runs inside the test process", worker_running(), False)
    expect("stats report the worker state", after["worker_running"], False)


def main() -> int:
    queued_elsewhere = count_claimable()
    if queued_elsewhere:
        print(
            f"refusing to run: {queued_elsewhere} other job(s) are already claimable, and the claim\n"
            "is global, so they would be taken ahead of this fixture's jobs. Let the ticket worker\n"
            "drain the queue (or stop it) and re-run."
        )
        return 1

    ticket_id = create_test_ticket()
    worker = "test-worker"

    try:
        test_claim_takes_the_oldest_ready_job(ticket_id, worker)
        test_claim_skips_a_job_that_is_backing_off(ticket_id, worker)
        test_claim_leaves_a_live_claim_alone(ticket_id, worker)
        test_claim_reclaims_a_job_whose_worker_died(ticket_id, worker)
        test_concurrent_workers_never_share_a_job(ticket_id)
        test_complete_marks_a_job_done(ticket_id, worker)
        test_fail_retries_with_backoff_then_gives_up(ticket_id)
        test_run_job_survives_a_deleted_ticket(uuid4())
        test_enqueue_shares_the_callers_transaction(ticket_id)
        test_queue_stats_tracks_depth(ticket_id)
    finally:
        with SyncSessionLocal() as db:
            # Jobs cascade with the ticket, but a job left behind by a partial
            # run must not survive to be claimed by the app.
            db.execute(delete(TicketJob).where(TicketJob.ticket_id == ticket_id))
            db.execute(delete(Ticket).where(Ticket.customer_id == TEST_CUSTOMER_ID))
            db.commit()

    if FAILURES:
        print(f"{len(FAILURES)} of {CHECKS} checks failed:\n")
        for failure in FAILURES:
            print(f"  {failure}")
        return 1

    print(f"{CHECKS}/{CHECKS} checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
