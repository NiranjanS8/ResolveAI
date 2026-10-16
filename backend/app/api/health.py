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


def _check_redis() -> dict:
    """Probe Redis when a client is available.

    Redis is configured but not yet used by the application, and its client is
    not a hard dependency, so a missing client or an unreachable server is
    reported without degrading the service.
    """
    try:
        from redis import Redis
    except ModuleNotFoundError:
        return {"ok": False, "detail": "redis client not installed"}

    try:
        client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        client.close()
        return {"ok": True, "detail": None}
    except Exception as exc:
        logger.warning("health: redis unreachable: %s", exc)
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
        "redis": _check_redis(),
        "providers": providers,
        "provider_configured": any(providers.values()),
    }
