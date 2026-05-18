from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.rag.embeddings import EmbeddingService, get_embedding_service
from app.storage.minio import StorageProtocol

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[EmbeddingService, Depends(get_embedding_service)]


def get_storage(request: Request) -> StorageProtocol | None:
    return request.app.state.storage


StorageDep = Annotated[StorageProtocol | None, Depends(get_storage)]


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        yield client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
