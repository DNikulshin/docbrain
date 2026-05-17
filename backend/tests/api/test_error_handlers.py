from __future__ import annotations

from httpx import AsyncClient

from app.main import app
from app.rag.embeddings import EmbeddingService, get_embedding_service


class _RaisingEmbedder:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise self._exc


def _override_embedder(exc: BaseException) -> EmbeddingService:
    embedder = _RaisingEmbedder(exc)
    app.dependency_overrides[get_embedding_service] = lambda: embedder
    return embedder


async def test_unsupported_format_returns_415(async_client: AsyncClient) -> None:
    files = {"file": ("data.bin", b"\x00\x01\x02", "application/octet-stream")}
    response = await async_client.post("/api/documents", files=files)

    assert response.status_code == 415
    assert response.json()["detail"].startswith("unsupported file extension")


async def test_value_error_returns_400(async_client: AsyncClient) -> None:
    _override_embedder(ValueError("bad batch"))
    files = {"file": ("ok.txt", b"hello", "text/plain")}
    response = await async_client.post("/api/documents", files=files)

    assert response.status_code == 400
    assert response.json() == {"detail": "bad batch"}


async def test_unicode_decode_error_returns_400(async_client: AsyncClient) -> None:
    _override_embedder(UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid start byte"))
    files = {"file": ("ok.txt", b"hello", "text/plain")}
    response = await async_client.post("/api/documents", files=files)

    assert response.status_code == 400
    assert "invalid start byte" in response.json()["detail"]


async def test_unhandled_exception_returns_500_with_request_id(
    async_client: AsyncClient,
) -> None:
    _override_embedder(RuntimeError("oops"))
    files = {"file": ("ok.txt", b"hello", "text/plain")}
    response = await async_client.post("/api/documents", files=files)

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal Server Error"
    assert body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]
