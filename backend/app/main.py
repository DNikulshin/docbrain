from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


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
