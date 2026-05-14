import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Chunk, Document
from app.parsers import UnsupportedFormatError
from app.rag.embeddings import StubEmbeddingService
from app.services.documents import (
    create_document,
    delete_document,
    get_document,
    list_documents,
)


def _stub() -> StubEmbeddingService:
    return StubEmbeddingService()


async def _bump_created_at(session: AsyncSession, doc: Document, *, seconds_ago: float) -> None:
    """Сдвинуть created_at назад на N секунд.

    Внутри одной транзакции func.now() возвращает одинаковое время на все INSERT'ы;
    в проде каждая загрузка — своя транзакция. В тестах подменяем явно, чтобы
    ORDER BY created_at был детерминирован.
    """
    doc.created_at = datetime.now(UTC) - timedelta(seconds=seconds_ago)
    await session.flush()


async def test_create_document_persists_document_and_chunks(db_session: AsyncSession) -> None:
    payload = ("a" * 2000).encode("utf-8")

    doc = await create_document(
        db_session,
        filename="big.txt",
        content_type="text/plain",
        payload=payload,
        embedder=_stub(),
    )

    assert doc.id is not None
    assert doc.name == "big.txt"
    assert doc.content_type == "text/plain"
    assert doc.source is None

    chunks = (
        await db_session.scalars(
            select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.ord)
        )
    ).all()
    assert [c.ord for c in chunks] == [0, 1, 2]
    for chunk in chunks:
        assert chunk.document_id == doc.id
        assert len(chunk.embedding) == settings.embedding_dim


async def test_create_document_short_text_single_chunk(db_session: AsyncSession) -> None:
    doc = await create_document(
        db_session,
        filename="tiny.txt",
        content_type="text/plain",
        payload=b"hello world",
        embedder=_stub(),
    )

    chunks = (await db_session.scalars(select(Chunk).where(Chunk.document_id == doc.id))).all()
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"


async def test_create_document_empty_payload_creates_doc_no_chunks(
    db_session: AsyncSession,
) -> None:
    doc = await create_document(
        db_session,
        filename="empty.txt",
        content_type="text/plain",
        payload=b"",
        embedder=_stub(),
    )

    chunks = (await db_session.scalars(select(Chunk).where(Chunk.document_id == doc.id))).all()
    assert chunks == []


async def test_create_document_markdown_strips_frontmatter(db_session: AsyncSession) -> None:
    payload = b"---\ntitle: Test\n---\n# Hello\n\nBody text."

    doc = await create_document(
        db_session,
        filename="note.md",
        content_type="text/markdown",
        payload=payload,
        embedder=_stub(),
    )

    chunks = (
        await db_session.scalars(
            select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.ord)
        )
    ).all()
    assert len(chunks) == 1
    assert "title: Test" not in chunks[0].text
    assert "# Hello" in chunks[0].text


async def test_create_document_unsupported_format_raises(db_session: AsyncSession) -> None:
    with pytest.raises(UnsupportedFormatError):
        await create_document(
            db_session,
            filename="binary.bin",
            content_type="application/octet-stream",
            payload=b"\x00\x01\x02",
            embedder=_stub(),
        )

    docs = (await db_session.scalars(select(Document))).all()
    assert docs == []


async def test_list_documents_orders_by_created_at_desc(db_session: AsyncSession) -> None:
    first = await create_document(
        db_session,
        filename="first.txt",
        content_type="text/plain",
        payload=b"first",
        embedder=_stub(),
    )
    await _bump_created_at(db_session, first, seconds_ago=10)
    second = await create_document(
        db_session,
        filename="second.txt",
        content_type="text/plain",
        payload=b"second",
        embedder=_stub(),
    )
    await _bump_created_at(db_session, second, seconds_ago=1)

    docs = await list_documents(db_session)
    ids = [d.id for d in docs]
    assert ids.index(second.id) < ids.index(first.id)


async def test_list_documents_pagination(db_session: AsyncSession) -> None:
    first = await create_document(
        db_session,
        filename="a.txt",
        content_type="text/plain",
        payload=b"a",
        embedder=_stub(),
    )
    await _bump_created_at(db_session, first, seconds_ago=10)
    second = await create_document(
        db_session,
        filename="b.txt",
        content_type="text/plain",
        payload=b"b",
        embedder=_stub(),
    )
    await _bump_created_at(db_session, second, seconds_ago=1)

    page = await list_documents(db_session, limit=1, offset=1)
    assert len(page) == 1
    assert page[0].id == first.id


async def test_get_document_returns_doc(db_session: AsyncSession) -> None:
    doc = await create_document(
        db_session,
        filename="x.txt",
        content_type="text/plain",
        payload=b"x",
        embedder=_stub(),
    )

    found = await get_document(db_session, doc.id)
    assert found is not None
    assert found.id == doc.id


async def test_get_document_missing_returns_none(db_session: AsyncSession) -> None:
    assert await get_document(db_session, uuid.uuid4()) is None


async def test_delete_document_cascades_chunks(db_session: AsyncSession) -> None:
    doc = await create_document(
        db_session,
        filename="del.txt",
        content_type="text/plain",
        payload=b"to be deleted",
        embedder=_stub(),
    )
    doc_id = doc.id

    ok = await delete_document(db_session, doc_id)
    assert ok is True

    assert await get_document(db_session, doc_id) is None
    chunks = (await db_session.scalars(select(Chunk).where(Chunk.document_id == doc_id))).all()
    assert chunks == []

    assert await delete_document(db_session, doc_id) is False
