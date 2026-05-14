from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk
from app.rag.embeddings import EmbeddingService
from app.rag.retriever import search as search_chunks


async def search_documents(
    session: AsyncSession,
    *,
    query: str,
    top_k: int,
    embedder: EmbeddingService,
) -> list[tuple[Chunk, float]]:
    [query_vector] = await embedder.embed([query])
    return await search_chunks(session, query_embedding=query_vector, top_k=top_k)
