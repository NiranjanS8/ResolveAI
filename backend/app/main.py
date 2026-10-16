import sys
import asyncio

# CRITICAL: Set event loop policy BEFORE any other imports
# This must be at the very top to work with uvicorn subprocesses
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.tickets import router as tickets_router
from app.api.analytics import router as analytics_router
from app.core.config import settings
from app.db.session import sync_engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - use sync engine to avoid psycopg v3 async issues on Windows
    Base.metadata.create_all(bind=sync_engine)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(tickets_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)