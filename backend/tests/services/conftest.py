from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Сессия поверх внешней транзакции с rollback в конце теста.

    Свой engine на каждый тест (NullPool, без переиспользования соединений) —
    модульный engine из app.db.session привязан к event loop'у первого теста,
    а pytest-asyncio создаёт новый loop на каждую функцию.

    join_transaction_mode="create_savepoint": commit() внутри сервиса
    превращается в RELEASE SAVEPOINT, внешний rollback всё равно отыграет.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await engine.dispose()
