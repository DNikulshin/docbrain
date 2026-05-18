from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Chunk, Document
from app.parsers import parse
from app.rag.chunker import split_text
from app.rag.embeddings import EmbeddingService, get_embedding_service
from app.storage.minio import StorageProtocol

logger = structlog.get_logger(__name__)


async def create_document(
    session: AsyncSession,
    *,
    filename: str,
    content_type: str,
    payload: bytes,
    storage: StorageProtocol | None = None,
    embedder: EmbeddingService | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> tuple[Document, int]:
    logger.info("document_create_start", filename=filename, size=len(payload))

    text = parse(filename, payload)

    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
    chunks_text = split_text(text, size=size, overlap=overlap)

    embedder = embedder if embedder is not None else get_embedding_service()
    vectors = await embedder.embed(chunks_text)

    doc_id = uuid.uuid4()
    source: str | None = None
    if storage is not None:
        key = f"{doc_id}/{filename}"
        await storage.put_object(key, payload, content_type)
        source = f"s3://{settings.minio_bucket}/{key}"

    document = Document(id=doc_id, name=filename, content_type=content_type, source=source)
    session.add(document)
    for ord_, (chunk_text, vector) in enumerate(zip(chunks_text, vectors, strict=True)):
        document.chunks.append(
            Chunk(ord=ord_, text=chunk_text, embedding=vector),
        )

    await session.flush()
    await session.commit()
    await session.refresh(document)

    logger.info("document_create_done", document_id=str(document.id), chunks=len(chunks_text))
    return document, len(chunks_text)


async def create_document_from_url(
    session: AsyncSession,
    *,
    url: str,
    text: str,
    filename: str,
    content_type: str,
    raw_bytes: bytes,
    storage: StorageProtocol | None = None,
    embedder: EmbeddingService | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> tuple[Document, int]:
    logger.info("document_url_create_start", url=url, size=len(raw_bytes))

    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
    chunks_text = split_text(text, size=size, overlap=overlap)

    embedder = embedder if embedder is not None else get_embedding_service()
    vectors = await embedder.embed(chunks_text)

    doc_id = uuid.uuid4()
    source: str | None = None
    if storage is not None:
        key = f"url/{doc_id}/{filename}"
        await storage.put_object(key, raw_bytes, content_type)
        source = f"s3://{settings.minio_bucket}/{key}"

    document = Document(id=doc_id, name=filename, content_type=content_type, source=source)
    session.add(document)
    for ord_, (chunk_text, vector) in enumerate(zip(chunks_text, vectors, strict=True)):
        document.chunks.append(
            Chunk(ord=ord_, text=chunk_text, embedding=vector),
        )

    await session.flush()
    await session.commit()
    await session.refresh(document)

    logger.info("document_url_create_done", document_id=str(document.id), chunks=len(chunks_text))
    return document, len(chunks_text)


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
    storage: StorageProtocol | None = None,
) -> bool:
    document = await session.get(Document, document_id)
    if document is None:
        return False

    source = document.source
    await session.delete(document)
    await session.commit()

    if storage is not None and source and source.startswith("s3://"):
        key = source.removeprefix(f"s3://{settings.minio_bucket}/")
        try:
            await storage.delete_object(key)
        except Exception:
            logger.warning("storage_delete_failed", key=key)

    return True
