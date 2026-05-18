import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document


@pytest.fixture
def configured_api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "docbrain_api_key", "test-secret-key")
    return "test-secret-key"


async def test_import_new_file(async_client: AsyncClient, db_session: AsyncSession) -> None:
    files = {"file": ("hello.txt", b"hello world from google drive", "text/plain")}
    data = {"file_id": "gdrive-file-001"}

    response = await async_client.post("/api/import/gdrive", files=files, data=data)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "created"
    assert body["document"]["name"] == "hello.txt"
    assert body["document"]["chunks_count"] >= 1

    doc = await db_session.get(Document, uuid.UUID(body["document"]["id"]))
    assert doc is not None
    assert doc.source_id == "gdrive:gdrive-file-001"


async def test_import_replace(async_client: AsyncClient, db_session: AsyncSession) -> None:
    files_v1 = {"file": ("doc.txt", b"version one content", "text/plain")}
    data = {"file_id": "gdrive-file-002"}

    r1 = await async_client.post("/api/import/gdrive", files=files_v1, data=data)
    assert r1.status_code == 201
    old_id = uuid.UUID(r1.json()["document"]["id"])

    files_v2 = {"file": ("doc_v2.txt", b"version two updated content", "text/plain")}
    r2 = await async_client.post("/api/import/gdrive", files=files_v2, data=data)

    assert r2.status_code == 201
    body = r2.json()
    assert body["status"] == "replaced"
    new_id = uuid.UUID(body["document"]["id"])
    assert new_id != old_id
    assert body["document"]["name"] == "doc_v2.txt"

    old_doc = await db_session.get(Document, old_id)
    assert old_doc is None

    new_doc = await db_session.get(Document, new_id)
    assert new_doc is not None
    assert new_doc.source_id == "gdrive:gdrive-file-002"


async def test_import_wrong_api_key(async_client: AsyncClient, configured_api_key: str) -> None:
    files = {"file": ("x.txt", b"content", "text/plain")}
    data = {"file_id": "gdrive-file-003"}

    response = await async_client.post(
        "/api/import/gdrive",
        files=files,
        data=data,
        headers={"X-API-Key": "wrong-key"},
    )

    assert response.status_code == 403


async def test_import_no_api_key_when_key_configured(
    async_client: AsyncClient, configured_api_key: str
) -> None:
    files = {"file": ("x.txt", b"content", "text/plain")}
    data = {"file_id": "gdrive-file-004"}

    response = await async_client.post("/api/import/gdrive", files=files, data=data)

    assert response.status_code == 403


async def test_import_no_api_key_when_not_configured(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    # settings.docbrain_api_key is None by default — dev mode, no auth
    assert settings.docbrain_api_key is None

    files = {"file": ("x.txt", b"dev mode content", "text/plain")}
    data = {"file_id": "gdrive-file-005"}

    response = await async_client.post("/api/import/gdrive", files=files, data=data)

    assert response.status_code == 201
    assert response.json()["status"] == "created"
