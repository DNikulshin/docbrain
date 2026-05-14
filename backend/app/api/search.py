from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import EmbedderDep, SessionDep
from app.schemas.search import SearchHit, SearchRequest
from app.services.search import search_documents

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[SearchHit])
async def search_endpoint(
    body: SearchRequest,
    session: SessionDep,
    embedder: EmbedderDep,
) -> list[SearchHit]:
    hits = await search_documents(
        session,
        query=body.query,
        top_k=body.top_k,
        embedder=embedder,
    )
    return [
        SearchHit(
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            ord=chunk.ord,
            text=chunk.text,
            distance=dist,
        )
        for chunk, dist in hits
    ]
