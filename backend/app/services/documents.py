from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Chunk, Document
from app.parsers import parse
from app.rag.chunker import split_text
from app.rag.embeddings import EmbeddingService, get_embedding_service


async def create_document(
    session: AsyncSession,
    *,
    filename: str,
    content_type: str,
    payload: bytes,
    source: str | None = None,
    embedder: EmbeddingService | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> Document:
    text = parse(filename, payload)

    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
    chunks_text = split_text(text, size=size, overlap=overlap)

    embedder = embedder if embedder is not None else get_embedding_service()
    vectors = await embedder.embed(chunks_text)

    document = Document(name=filename, content_type=content_type, source=source)
    session.add(document)
    for ord_, (chunk_text, vector) in enumerate(zip(chunks_text, vectors, strict=True)):
        document.chunks.append(
            Chunk(ord=ord_, text=chunk_text, embedding=vector),
        )

    await session.flush()
    await session.commit()
    await session.refresh(document)
    return document


async def list_documents(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    result = await session.scalars(stmt)
    return list(result.all())


async def get_document(
    session: AsyncSession,
    document_id: uuid.UUID,
) -> Document | None:
    return await session.get(Document, document_id)


async def delete_document(
    session: AsyncSession,
    document_id: uuid.UUID,
) -> bool:
    document = await session.get(Document, document_id)
    if document is None:
        return False
    await session.delete(document)
    await session.commit()
    return True
