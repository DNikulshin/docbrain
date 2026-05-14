from fastapi import FastAPI
from sqlalchemy import text

from app.api.deps import SessionDep
from app.api.documents import router as documents_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(documents_router, prefix="/api")


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
