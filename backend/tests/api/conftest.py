from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.main import app


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """ASGI-клиент, привязанный к той же транзакции, что и db_session.

    Переопределяем get_session так, чтобы ручка использовала тестовую сессию
    с rollback в конце теста — без этого роутер открыл бы свою AsyncSession
    через модульный engine, и rollback фикстуры не достал бы его изменения.
    """

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
