from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_storage
from app.db.session import get_session
from app.main import app
from app.storage.minio import StubStorage


@pytest_asyncio.fixture
async def stub_storage() -> StubStorage:
    return StubStorage()


@pytest_asyncio.fixture
async def async_client(
    db_session: AsyncSession, stub_storage: StubStorage
) -> AsyncIterator[AsyncClient]:
    """ASGI-клиент с тестовой БД-сессией и in-memory StubStorage."""

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_storage] = lambda: stub_storage
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
