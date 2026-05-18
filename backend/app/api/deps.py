from typing import Annotated

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
