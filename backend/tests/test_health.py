from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "docbrain-backend"
    assert "version" in body
    assert "environment" in body


def test_health_db_with_vector_installed(client: TestClient) -> None:
    """SELECT 1 → 1, SELECT extversion → '0.8.2' (pgvector установлен)."""
    session = AsyncMock()
    session.execute.side_effect = [
        AsyncMock(scalar_one=lambda: 1),
        AsyncMock(scalar_one_or_none=lambda: "0.8.2"),
    ]

    async def override_get_session() -> AsyncIterator[AsyncMock]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "pgvector": "0.8.2"}


def test_health_db_without_pgvector(client: TestClient) -> None:
    """БД жива, но расширение vector ещё не установлено → status=degraded."""
    session = AsyncMock()
    session.execute.side_effect = [
        AsyncMock(scalar_one=lambda: 1),
        AsyncMock(scalar_one_or_none=lambda: None),
    ]

    async def override_get_session() -> AsyncIterator[AsyncMock]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "db": "ok", "pgvector": "missing"}
