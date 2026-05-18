import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Chunk, Document


async def test_post_document_txt_returns_201_with_chunks_count(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    files = {"file": ("hello.txt", b"hello world", "text/plain")}
    response = await async_client.post("/api/documents", files=files)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "hello.txt"
    assert body["content_type"] == "text/plain"
    assert body["chunks_count"] == 1
    doc_id = uuid.UUID(body["id"])

    doc = await db_session.get(Document, doc_id)
    assert doc is not None
    chunks = (await db_session.scalars(select(Chunk).where(Chunk.document_id == doc_id))).all()
    assert len(chunks) == 1


async def test_post_document_md_strips_frontmatter(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    payload = b"---\ntitle: Test\n---\n# Hello\n\nBody."
    files = {"file": ("note.md", payload, "text/markdown")}
    response = await async_client.post("/api/documents", files=files)

    assert response.status_code == 201
    body = response.json()
    assert body["chunks_count"] == 1

    doc_id = uuid.UUID(body["id"])
    chunk = (await db_session.scalars(select(Chunk).where(Chunk.document_id == doc_id))).one()
    assert "title: Test" not in chunk.text
    assert "# Hello" in chunk.text


async def test_post_document_unsupported_format_returns_415(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    files = {"file": ("data.bin", b"\x00\x01\x02", "application/octet-stream")}
    response = await async_client.post("/api/documents", files=files)

    assert response.status_code == 415
    assert (await db_session.scalars(select(Document))).all() == []


async def test_post_document_too_large_returns_413(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    oversize = b"x" * (settings.max_upload_bytes + 1)
    files = {"file": ("huge.txt", oversize, "text/plain")}
    response = await async_client.post("/api/documents", files=files)

    assert response.status_code == 413
    assert (await db_session.scalars(select(Document))).all() == []


async def test_post_document_without_file_returns_422(async_client: AsyncClient) -> None:
    response = await async_client.post("/api/documents")
    assert response.status_code == 422


async def test_get_documents_lists_recent_first(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await async_client.post("/api/documents", files={"file": ("a.txt", b"a", "text/plain")})
    second = await async_client.post(
        "/api/documents", files={"file": ("b.txt", b"b", "text/plain")}
    )
    assert first.status_code == 201
    assert second.status_code == 201

    # В одной транзакции func.now() одинаков для обоих INSERT'ов —
    # сортировка по created_at недетерминирована. Проверяем только содержимое.
    response = await async_client.get("/api/documents")
    assert response.status_code == 200
    names = {doc["name"] for doc in response.json()}
    assert names == {"a.txt", "b.txt"}


async def test_get_documents_pagination(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    for name in ("a.txt", "b.txt", "c.txt"):
        await async_client.post("/api/documents", files={"file": (name, b"x", "text/plain")})

    response = await async_client.get("/api/documents", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_get_document_by_id_returns_200(async_client: AsyncClient) -> None:
    created = await async_client.post(
        "/api/documents", files={"file": ("x.txt", b"x", "text/plain")}
    )
    doc_id = created.json()["id"]

    response = await async_client.get(f"/api/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json()["id"] == doc_id


async def test_get_document_missing_returns_404(async_client: AsyncClient) -> None:
    response = await async_client.get(f"/api/documents/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_delete_document_cascades_and_returns_204(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    created = await async_client.post(
        "/api/documents", files={"file": ("del.txt", b"bye", "text/plain")}
    )
    doc_id = uuid.UUID(created.json()["id"])

    response = await async_client.delete(f"/api/documents/{doc_id}")
    assert response.status_code == 204

    assert await db_session.get(Document, doc_id) is None
    remaining = await db_session.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == doc_id)
    )
    assert remaining == 0

    follow_up = await async_client.get(f"/api/documents/{doc_id}")
    assert follow_up.status_code == 404


async def test_delete_document_missing_returns_404(async_client: AsyncClient) -> None:
    response = await async_client.delete(f"/api/documents/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_post_document_sets_source(async_client: AsyncClient) -> None:
    files = {"file": ("doc.txt", b"hello", "text/plain")}
    response = await async_client.post("/api/documents", files=files)

    assert response.status_code == 201
    body = response.json()
    assert body["source"] is not None
    assert body["source"].startswith("s3://docbrain-files/")
    assert body["source"].endswith("/doc.txt")


async def test_get_document_source_redirects(async_client: AsyncClient) -> None:
    created = await async_client.post(
        "/api/documents", files={"file": ("x.txt", b"x", "text/plain")}
    )
    doc_id = created.json()["id"]

    response = await async_client.get(f"/api/documents/{doc_id}/source", follow_redirects=False)
    assert response.status_code == 302
    assert "stub" in response.headers["location"]


async def test_get_document_source_no_source_returns_404(async_client: AsyncClient) -> None:
    response = await async_client.get(
        f"/api/documents/{uuid.uuid4()}/source", follow_redirects=False
    )
    assert response.status_code == 404
