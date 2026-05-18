from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import APIKeyDep, EmbedderDep, SessionDep, StorageDep
from app.config import settings
from app.schemas.document import DocumentCreatedRead, GdriveImportRead
from app.services.documents import import_gdrive_document

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/gdrive", response_model=GdriveImportRead, status_code=status.HTTP_201_CREATED)
async def import_gdrive(
    _: APIKeyDep,
    session: SessionDep,
    embedder: EmbedderDep,
    storage: StorageDep,
    file: Annotated[UploadFile, File(...)],
    file_id: Annotated[str, Form(...)],
) -> GdriveImportRead:
    payload = await file.read()
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds {settings.max_upload_bytes} bytes",
        )

    document, chunks_count, import_status = await import_gdrive_document(
        session,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        payload=payload,
        source_id=f"gdrive:{file_id}",
        storage=storage,
        embedder=embedder,
    )
    return GdriveImportRead(
        status=import_status,
        document=DocumentCreatedRead(
            id=document.id,
            name=document.name,
            content_type=document.content_type,
            source=document.source,
            created_at=document.created_at,
            chunks_count=chunks_count,
        ),
    )
