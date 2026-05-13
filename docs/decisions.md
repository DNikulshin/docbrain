# Архитектурные решения

Журнал принятых решений с датами. Новые записи — сверху.

## 2026-05-13 — Спринт 1: фундамент бэкенда

- **БД.** Отдельный контейнер `docbrain-db` на `pgvector/pgvector:pg16` (вариант 2 из [INFRA.md §3](../INFRA.md)). Старая `db_docbrain` в общем `postgres-provision` не используется — там нет расширения `vector`. Старый `.env` сохранён локально как `.env.old.bak` (gitignored).
- **ORM/миграции.** SQLAlchemy 2.x async + asyncpg, alembic в async-режиме (`async_engine_from_config` + `run_sync`). Пока нет SQLAlchemy-моделей — `target_metadata = None`, миграции пишем вручную; autogenerate включим, когда появятся модели.
- **Применение миграций.** `alembic upgrade head` запускается автоматически в `backend/docker-entrypoint.sh` перед `uvicorn`. `depends_on: condition: service_healthy` гарантирует, что БД готова.
- **Health-эндпоинты.** Два уровня: `GET /health` (только сервис, без БД, дёшев для проб) и `GET /health/db` (`SELECT 1` + версия `vector`). `GET /health/db` использует `Annotated[AsyncSession, Depends(get_session)]`.
- **Стиль кода.** Ruff как единый линтер+форматер (`E/W/F/I/B/UP/ASYNC/SIM`, line=100). `target-version = "py311"`.
- **Тесты.** pytest + `pytest-asyncio` (`asyncio_mode=auto`, `asyncio_default_fixture_loop_scope=function`). Интеграционные тесты на эндпоинты — через `TestClient` и `app.dependency_overrides` для подмены `get_session`. `tests/conftest.py` подставляет фейковый `DATABASE_URL` до импортов app, чтобы юниты не требовали `.env`.
- **Docker.** Многостадийный Dockerfile: `base` (зависимости) → `dev` (+ dev-deps, `--reload`) → `prod`. `ENTRYPOINT ["sh", "./docker-entrypoint.sh"]` — не зависит от executable-бита, который теряется при bind-mount.

## 2026-05-13 — Согласовано на старте проекта

- **Авторизация веб-чата.** JWT в FastAPI, не Authelia. Telegram-бот идентифицирует пользователей по `chat_id`.
- **n8n импорт.** Pull-mode каждые 6 часов из Google Drive (см. README §«Шаг 6»). n8n — за Authelia.
- **Telegram-webhook — публичный.** Без `import authelia` (Telegram не умеет SSO). Префикс `/tg/webhook*` отдельным `handle` в Caddyfile.
- **OpenRouter.** Один API-ключ на сервис (single-tenant на старте).
- **MinIO.** Переиспользуем существующий инстанс, бакет `docbrain-files`.
- **Git/коммиты.** Conventional Commits, основная ветка `main`, remote `github.com/DNikulshin/docbrain`.
