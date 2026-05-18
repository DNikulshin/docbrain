from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient

from app.api.deps import get_http_client

_HTML = b"""
<html><head><title>Test page</title></head>
<body><article><p>Paragraph with enough text to form at least one chunk in the document.</p>
<p>More content here to ensure chunking works correctly in the test.</p></article></body>
</html>
"""

_HTML_CT = "text/html"


def _make_http_override(content: bytes, content_type: str, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=content, headers={"content-type": content_type})

    mock_transport = httpx.MockTransport(handler)

    async def override():
        async with httpx.AsyncClient(transport=mock_transport) as client:
            yield client

    return override


@pytest.mark.asyncio
async def test_post_url_html_returns_201(async_client: AsyncClient):
    from app.main import app

    app.dependency_overrides[get_http_client] = _make_http_override(_HTML, _HTML_CT)
    try:
        resp = await async_client.post(
            "/api/documents/url", json={"url": "http://example.com/page"}
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert resp.status_code == 201
    data = resp.json()
    assert data["chunks_count"] >= 1
    assert data["name"]
    assert data["content_type"] == _HTML_CT


@pytest.mark.asyncio
async def test_post_url_source_is_s3_uri(async_client: AsyncClient):
    from app.main import app

    app.dependency_overrides[get_http_client] = _make_http_override(_HTML, _HTML_CT)
    try:
        resp = await async_client.post("/api/documents/url", json={"url": "http://example.com/"})
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert resp.status_code == 201
    source = resp.json().get("source")
    assert source is not None
    assert source.startswith("s3://")
    assert "/url/" in source


@pytest.mark.asyncio
async def test_post_url_invalid_url_returns_422(async_client: AsyncClient):
    resp = await async_client.post("/api/documents/url", json={"url": "not-a-url"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_url_missing_body_returns_422(async_client: AsyncClient):
    resp = await async_client.post("/api/documents/url", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_url_size_exceeded_returns_400(async_client: AsyncClient):
    from app.main import app

    big_content = b"x" * (11 * 1024 * 1024)
    app.dependency_overrides[get_http_client] = _make_http_override(big_content, "text/html")
    try:
        resp = await async_client.post("/api/documents/url", json={"url": "http://example.com/big"})
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert resp.status_code == 400
    assert "size limit" in resp.json()["detail"]
