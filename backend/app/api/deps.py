from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.rag.embeddings import EmbeddingService, get_embedding_service

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[EmbeddingService, Depends(get_embedding_service)]
