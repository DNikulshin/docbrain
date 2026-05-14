# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Общаться с пользователем на русском (см. `~/.claude/CLAUDE.md`). Стиль: чёткий, без воды.

## О проекте

DocBrain — RAG-консультант по документации: FastAPI + Next.js 15 + n8n (Google Drive sync) + PostgreSQL/pgvector + MinIO + Telegram-бот. Эмбеддинги/LLM через OpenRouter.

## Доки (читать ДО кода)

- [README.md](README.md) — продуктовый план, целевая структура, шаги деплоя.
- [INFRA.md](INFRA.md) — VPS, Caddy, Authelia, MinIO, Postgres, что НЕ трогать.
- [docs/decisions.md](docs/decisions.md) — журнал архитектурных решений с датами.
- [docs/dev.md](docs/dev.md) — команды разработки, нюансы окружения, FAQ.
- [docs/sprint-2-plan.md](docs/sprint-2-plan.md) — текущий спринт.

## Что сейчас работает

Спринт 1 закрыт (2026-05-13). `docker-compose up -d --build` поднимает `docbrain-db` (PG16 + pgvector 0.8.2) и `docbrain-backend` (FastAPI 0.115). Эндпоинты `/health` и `/health/db` отвечают.

Спринт 2 в работе. Шаги 2.1–2.6 закрыты:

- **2.1** (2026-05-13) — миграция `0002_documents_and_chunks` создала таблицы `documents` и `chunks` с `vector(1536)` и HNSW-индексом под cosine; SQLAlchemy-модели `Document`/`Chunk` подключены в `Base.metadata`.
- **2.2** (2026-05-13) — наивный char-based chunker [backend/app/rag/chunker.py](backend/app/rag/chunker.py): `split_text(text, size=800, overlap=100) -> list[str]`. Валидирует `size>0`, `0<=overlap<size` (raise `ValueError`). Реэкспорт из `app.rag`.
- **2.3** (2026-05-14) — embedding service [backend/app/rag/embeddings.py](backend/app/rag/embeddings.py): `EmbeddingService` Protocol, `StubEmbeddingService` (shake_256 → нормализованный вектор размерности `settings.embedding_dim`), `OpenRouterEmbeddingService` (заглушка с `NotImplementedError`), фабрика `get_embedding_service()` по `settings.embedding_provider`.
- **2.4** (2026-05-14) — парсеры [backend/app/parsers/](backend/app/parsers/): `parse(filename, payload) -> str` с диспатчем по расширению (`.txt`/`.md`/`.markdown`), `parse_markdown` срезает YAML-frontmatter, `UnsupportedFormatError(ValueError)` на неизвестных расширениях.
- **2.5** (2026-05-14) — сервисный слой [backend/app/services/documents.py](backend/app/services/documents.py): `create_document` склеивает `parse → split_text → embed → INSERT(Document + Chunks)` в одной транзакции; `list/get/delete_document` (каскадно). Pydantic v2 схемы — [backend/app/schemas/document.py](backend/app/schemas/document.py) (`DocumentCreate`, `DocumentRead`, `ChunkRead`). Integration-тесты — на живом `docbrain-db` через rollback-фикстуру (внешняя транзакция + `join_transaction_mode="create_savepoint"`, отдельный engine с `NullPool` чтобы обойти «event loop closed» в pytest-asyncio).
- **2.6** (2026-05-14) — API [backend/app/api/documents.py](backend/app/api/documents.py): `POST /api/documents` (multipart, 201 → `DocumentCreatedRead` с `chunks_count`), `GET /api/documents?limit=&offset=`, `GET /api/documents/{id}`, `DELETE /api/documents/{id}` (204). Лимит 10 МБ — 413, неизвестный формат — 415. `create_document` теперь отдаёт `(Document, int)`. Зависимости (`SessionDep`, `EmbedderDep`) — в [backend/app/api/deps.py](backend/app/api/deps.py). API-тесты — `httpx.AsyncClient + ASGITransport` поверх той же rollback-фикстуры; `db_session` переехал из `tests/services/conftest.py` в [backend/tests/conftest.py](backend/tests/conftest.py). Добавлен `python-multipart` в `requirements.txt`.

68 тестов зелёные. Следующий шаг — 2.7 (retriever + `/api/search`). Детали — в [docs/sprint-2-plan.md](docs/sprint-2-plan.md). Команды — в [docs/dev.md](docs/dev.md).

## Стиль работы

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`). Основная ветка — `main`, remote `github.com/DNikulshin/docbrain`.
- **Перед коммитом** обязательно: `ruff check .`, `ruff format --check .`, `pytest -v` — все внутри контейнера (см. [docs/dev.md](docs/dev.md)).
- **Не трогать** `.env` (живые пароли, gitignored), корневой `/opt/home-codespaces/docker-compose.yml`, контейнеры `portfolio-next-*`, `3xui-*`, `postgres-provision`. Подробнее — в [INFRA.md](INFRA.md).
- **Шаг — тест — коммит.** Не накапливать коммиты на 5 шагов вперёд.
