from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embeddings import StubEmbeddingService
from app.services.documents import create_document
from app.services.search import search_documents


def _stub() -> StubEmbeddingService:
    return StubEmbeddingService()


async def test_search_returns_top1_matching_document(db_session: AsyncSession) -> None:
    alpha_text = "alpha document content about pgvector"
    beta_text = "beta document content about kubernetes"

    alpha, _ = await create_document(
        db_session,
        filename="alpha.txt",
        content_type="text/plain",
        payload=alpha_text.encode("utf-8"),
        embedder=_stub(),
    )
    await create_document(
        db_session,
        filename="beta.txt",
        content_type="text/plain",
        payload=beta_text.encode("utf-8"),
        embedder=_stub(),
    )

    hits = await search_documents(
        db_session,
        query=alpha_text,
        top_k=5,
        embedder=_stub(),
    )

    assert len(hits) == 2
    top_chunk, top_distance = hits[0]
    assert top_chunk.document_id == alpha.id
    assert top_chunk.text == alpha_text
    assert top_distance < 1e-6
    # Второй документ — заметно дальше.
    assert hits[1][1] > top_distance


async def test_search_respects_top_k_limit(db_session: AsyncSession) -> None:
    # Маленькие чанки → много фрагментов из одного документа.
    payload = ("word " * 200).encode("utf-8")
    await create_document(
        db_session,
        filename="long.txt",
        content_type="text/plain",
        payload=payload,
        embedder=_stub(),
        chunk_size=50,
        chunk_overlap=10,
    )

    hits = await search_documents(
        db_session,
        query="word word word",
        top_k=3,
        embedder=_stub(),
    )
    assert len(hits) == 3


async def test_search_on_empty_db_returns_empty_list(db_session: AsyncSession) -> None:
    hits = await search_documents(
        db_session,
        query="anything",
        top_k=5,
        embedder=_stub(),
    )
    assert hits == []
