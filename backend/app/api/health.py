"""Liveness and dependency health.

Reports each dependency individually and returns 503 when the database — the one
the service cannot run without — is unreachable, so a broken service cannot
answer with a cheerful 200. Failures are logged with their cause.
"""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.core.providers import CHAT_PROVIDERS, is_configured

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_database() -> dict:
    from app.db.session import sync_engine

    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "detail": None}
    except Exception as exc:
        logger.error("health: database unreachable: %s", exc)
        return {"ok": False, "detail": str(exc)}


def _check_queue() -> dict:
    """Queue depth for ticket processing.

    Informational rather than fatal: the service still reads and enqueues while
    the worker catches up, so a backlog must not make the service look down.
    """
    from app.core.queue import queue_stats

    try:
        return queue_stats()
    except Exception as exc:
        logger.error("health: ticket queue unreadable: %s", exc)
        return {"ok": False, "detail": str(exc)}


@router.get("/health")
async def health_check(response: Response):
    database = _check_database()
    providers = {provider: is_configured(provider) for provider in CHAT_PROVIDERS}

    if not database["ok"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if database["ok"] else "degraded",
        "service": settings.PROJECT_NAME,
        "database": database,
        "queue": _check_queue(),
        "providers": providers,
        "provider_configured": any(providers.values()),
    }
