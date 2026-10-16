"""Audit-trail writer.

Lives in ``core`` rather than in the API layer because both the HTTP routes and
the synchronous graph nodes need to append entries, and the graph must not
import the API module (it would be a circular import).
"""

from uuid import uuid4

from sqlalchemy import insert as sa_insert

from app.db.session import SyncSessionLocal
from app.models.base import AuditLog


def log_audit_action(
    ticket_id,
    action: str,
    payload: dict,
    confidence=None,
    executed_by: str = "system",
) -> None:
    """Write an audit_log row via a sync session (used from synchronous graph code)."""
    with SyncSessionLocal() as audit_db:
        audit_db.execute(
            sa_insert(AuditLog.__table__).values(
                id=uuid4(),
                ticket_id=ticket_id,
                action=action,
                payload=payload,
                confidence=confidence,
                executed_by=executed_by,
            )
        )
        audit_db.commit()
