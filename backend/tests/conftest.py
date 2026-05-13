import os

# Тесты не должны зависеть от наличия .env. Подставляем безопасный фейк
# до первого импорта app.* — реального подключения здесь не происходит,
# /health не ходит в БД (для проверок БД отдельный эндпоинт /health/db).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)
