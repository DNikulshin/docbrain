from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.rag.embeddings import EmbeddingService, get_embedding_service
from app.storage.minio import StorageProtocol

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[EmbeddingService, Depends(get_embedding_service)]


async def verify_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if settings.docbrain_api_key is None:
        return
    if x_api_key != settings.docbrain_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="invalid or missing api key"
        )


APIKeyDep = Annotated[None, Depends(verify_api_key)]


def get_storage(request: Request) -> StorageProtocol | None:
    return request.app.state.storage


StorageDep = Annotated[StorageProtocol | None, Depends(get_storage)]


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        yield client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
