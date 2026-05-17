from fastapi import FastAPI
from sqlalchemy import text

from app.api.deps import SessionDep
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.config import settings
from app.logging_config import configure_logging
from app.middleware.request_context import RequestContextMiddleware

configure_logging(settings.log_level, settings.log_format)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(RequestContextMiddleware)

app.include_router(documents_router, prefix="/api")
app.include_router(search_router, prefix="/api")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/health/db", tags=["system"])
async def health_db(session: SessionDep) -> dict[str, object]:
    db_ok = (await session.execute(text("SELECT 1"))).scalar_one() == 1
    pgvector_version = (
        await session.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
    ).scalar_one_or_none()
    return {
        "status": "ok" if db_ok and pgvector_version else "degraded",
        "db": "ok" if db_ok else "fail",
        "pgvector": pgvector_version or "missing",
    }
