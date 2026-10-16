import asyncio

from fastapi import APIRouter, Query

from app.core.metrics import DEFAULT_RANGE, analytics_snapshot

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("")
async def get_analytics(
    range: str = Query(DEFAULT_RANGE, pattern="^(24h|7d|30d)$"),
):
    """Dashboard metrics, computed from the database by ``app.core.metrics``.

    The queries are synchronous, so they run in a thread to keep the aggregation
    off the event loop; the same snapshot function backs the CLI report.
    """
    return await asyncio.to_thread(analytics_snapshot, range)
