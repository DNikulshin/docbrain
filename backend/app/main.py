from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import SessionDep
from app.api.documents import router as documents_router
from app.api.import_ import router as import_router
from app.api.search import router as search_router
from app.config import settings
from app.logging_config import configure_logging
from app.middleware.request_context import RequestContextMiddleware
from app.parsers import UnsupportedFormatError
from app.storage.minio import MinioStorage

configure_logging(settings.log_level, settings.log_format)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.minio_endpoint:
        import aiobotocore.session as aio_session

        s = aio_session.get_session()
        kwargs = dict(
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name="us-east-1",
        )
        async with s.create_client("s3", endpoint_url=settings.minio_endpoint, **kwargs) as client:
            pub_url = settings.minio_public_endpoint or settings.minio_endpoint
            async with s.create_client("s3", endpoint_url=pub_url, **kwargs) as pub_client:
                app.state.storage = MinioStorage(
                    client,
                    pub_client,
                    bucket=settings.minio_bucket,
                    presign_ttl=settings.minio_presign_ttl_sec,
                )
                logger.info("minio_connected", bucket=settings.minio_bucket)
                yield
    else:
        app.state.storage = None
        logger.warning("minio_not_configured")
        yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)

app.include_router(documents_router, prefix="/api")
app.include_router(import_router, prefix="/api")
app.include_router(search_router, prefix="/api")


@app.exception_handler(UnsupportedFormatError)
async def unsupported_format_handler(
    _request: Request, exc: UnsupportedFormatError
) -> JSONResponse:
    logger.warning("unsupported_format", detail=str(exc))
    return JSONResponse(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        content={"detail": str(exc)},
    )


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    logger.warning("value_error", detail=str(exc))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(UnicodeDecodeError)
async def unicode_decode_error_handler(_request: Request, exc: UnicodeDecodeError) -> JSONResponse:
    logger.warning("unicode_decode_error", detail=str(exc))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
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


@app.get("/health/minio", tags=["system"])
async def health_minio() -> dict[str, object]:
    storage = app.state.storage
    if storage is None:
        return {"status": "not_configured"}
    ok = await storage.health()
    return {"status": "ok" if ok else "fail", "bucket": settings.minio_bucket}
