# api/main.py
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import docs_router, ingest_router, chat_router, brief_router, kb_router, session_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create query log directory at startup. Wrapped in try/except — if the
    # filesystem is read-only or permissions are wrong, the API should still start.
    # Chat will still work; _log_query silently skips writes on failure.
    try:
        log_dir = os.path.dirname(os.path.abspath(settings.query_log_path))
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        logger.warning("Could not create query log directory %r: %s — logging disabled", settings.query_log_path, e)

    # Warn if running multiple workers — file writes to query_log are not safe
    # for concurrent multi-worker deployments. Single-worker only for this iteration.
    workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
    if workers > 1:
        logger.warning(
            "WEB_CONCURRENCY=%d detected — query log file writes are not safe for "
            "multi-worker deployments. Set WEB_CONCURRENCY=1 or mount a per-worker "
            "QUERY_LOG_PATH to avoid log corruption.",
            workers,
        )

    yield


app = FastAPI(title="Career Lighthouse API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(docs_router.router)
app.include_router(ingest_router.router)
app.include_router(brief_router.router)
app.include_router(kb_router.router)
app.include_router(chat_router.router)
app.include_router(session_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
