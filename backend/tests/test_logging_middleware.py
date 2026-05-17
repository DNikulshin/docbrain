from __future__ import annotations

import pytest
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.request_context import RequestContextMiddleware


def _make_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    @test_app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    @test_app.get("/ctx")
    async def ctx() -> dict[str, str]:
        return structlog.contextvars.get_contextvars()

    return test_app


@pytest.fixture()
def test_app() -> FastAPI:
    return _make_test_app()


@pytest.mark.asyncio
async def test_request_id_generated_when_absent(test_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/ping")
    assert response.status_code == 200
    request_id = response.headers.get("X-Request-ID", "")
    assert len(request_id) > 0


@pytest.mark.asyncio
async def test_request_id_forwarded_when_present(test_app: FastAPI) -> None:
    custom_id = "my-custom-request-id-abc123"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/ping", headers={"X-Request-ID": custom_id})
    assert response.headers["X-Request-ID"] == custom_id


@pytest.mark.asyncio
async def test_request_id_in_structlog_contextvars(test_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/ctx")
    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert len(data["request_id"]) > 0
