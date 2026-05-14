from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk


async def search(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[tuple[Chunk, float]]:
    distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = select(Chunk, distance).order_by(distance).limit(top_k)
    result = await session.execute(stmt)
    return [(chunk, float(dist)) for chunk, dist in result.all()]
