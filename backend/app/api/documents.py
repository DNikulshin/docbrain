from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import RedirectResponse

from app.api.deps import EmbedderDep, HttpClientDep, SessionDep, StorageDep
from app.config import settings
from app.parsers.url import parse_url
from app.schemas.document import DocumentCreatedRead, DocumentRead, UrlIngest
from app.services.documents import (
    create_document,
    create_document_from_url,
    delete_document,
    get_document,
    list_documents,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentCreatedRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    session: SessionDep,
    embedder: EmbedderDep,
    storage: StorageDep,
    file: Annotated[UploadFile, File(...)],
) -> DocumentCreatedRead:
    payload = await file.read()
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds limit of {settings.max_upload_bytes} bytes",
        )

    document, chunks_count = await create_document(
        session,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        payload=payload,
        storage=storage,
        embedder=embedder,
    )

    return DocumentCreatedRead(
        id=document.id,
        name=document.name,
        content_type=document.content_type,
        source=document.source,
        created_at=document.created_at,
        chunks_count=chunks_count,
    )


@router.post(
    "/url",
    response_model=DocumentCreatedRead,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_url(
    body: UrlIngest,
    session: SessionDep,
    embedder: EmbedderDep,
    storage: StorageDep,
    http: HttpClientDep,
) -> DocumentCreatedRead:
    try:
        text, raw_bytes, filename, content_type = await parse_url(
            str(body.url), http, settings.max_upload_bytes
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document, chunks_count = await create_document_from_url(
        session,
        url=str(body.url),
        text=text,
        filename=filename,
        content_type=content_type,
        raw_bytes=raw_bytes,
        storage=storage,
        embedder=embedder,
    )

    return DocumentCreatedRead(
        id=document.id,
        name=document.name,
        content_type=document.content_type,
        source=document.source,
        created_at=document.created_at,
        chunks_count=chunks_count,
    )


@router.get("", response_model=list[DocumentRead])
async def list_documents_endpoint(
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[DocumentRead]:
    documents = await list_documents(session, limit=limit, offset=offset)
    return [DocumentRead.model_validate(doc) for doc in documents]


@router.get("/{document_id}/source", status_code=302)
async def get_document_source(
    document_id: uuid.UUID,
    session: SessionDep,
    storage: StorageDep,
) -> RedirectResponse:
    document = await get_document(session, document_id)
    if document is None or document.source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="storage not configured",
        )
    key = document.source.removeprefix(f"s3://{settings.minio_bucket}/")
    url = storage.generate_presigned_url(key, ttl=settings.minio_presign_ttl_sec)
    return RedirectResponse(url, status_code=302)


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document_endpoint(
    document_id: uuid.UUID,
    session: SessionDep,
) -> DocumentRead:
    document = await get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    document_id: uuid.UUID,
    session: SessionDep,
    storage: StorageDep,
) -> Response:
    deleted = await delete_document(session, document_id, storage=storage)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
