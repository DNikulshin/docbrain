from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk
from app.rag.embeddings import EmbeddingService
from app.rag.retriever import search as search_chunks

logger = structlog.get_logger(__name__)


async def search_documents(
    session: AsyncSession,
    *,
    query: str,
    top_k: int,
    embedder: EmbeddingService,
) -> list[tuple[Chunk, float]]:
    logger.info("search_query", top_k=top_k, query_len=len(query))
    [query_vector] = await embedder.embed([query])
    results = await search_chunks(session, query_embedding=query_vector, top_k=top_k)
    logger.info("search_done", hits=len(results))
    return results
