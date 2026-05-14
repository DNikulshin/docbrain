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

Спринт 2 в работе. Шаги 2.1, 2.2 (2026-05-13) и 2.3 (2026-05-14) закрыты:

- **2.1** — миграция `0002_documents_and_chunks` создала таблицы `documents` и `chunks` с `vector(1536)` и HNSW-индексом под cosine; SQLAlchemy-модели `Document`/`Chunk` подключены в `Base.metadata`.
- **2.2** — наивный char-based chunker [backend/app/rag/chunker.py](backend/app/rag/chunker.py): `split_text(text, size=800, overlap=100) -> list[str]`. Валидирует `size>0`, `0<=overlap<size` (raise `ValueError`). Реэкспорт из `app.rag`. 14 unit-тестов зелёные.
- **2.3** — embedding service [backend/app/rag/embeddings.py](backend/app/rag/embeddings.py): `EmbeddingService` Protocol + `StubEmbeddingService` (`shake_256` → L2-нормализованный `vector(settings.embedding_dim)`, детерминированно, без сетевых вызовов), заготовка `OpenRouterEmbeddingService` с `NotImplementedError` под спринт 3, фабрика `get_embedding_service()` по `settings.embedding_provider`. Реэкспорт из `app.rag`. 12 unit-тестов зелёные.

Сервисов, роутеров и парсеров пока нет. Следующий шаг — 2.4 (парсеры TXT/MD: `app/parsers/{base,text,markdown}.py`, диспатч по расширению, `UnsupportedFormatError`). Детали — в [docs/sprint-2-plan.md](docs/sprint-2-plan.md). Команды — в [docs/dev.md](docs/dev.md).

## Стиль работы

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`). Основная ветка — `main`, remote `github.com/DNikulshin/docbrain`.
- **Перед коммитом** обязательно: `ruff check .`, `ruff format --check .`, `pytest -v` — все внутри контейнера (см. [docs/dev.md](docs/dev.md)).
- **Не трогать** `.env` (живые пароли, gitignored), корневой `/opt/home-codespaces/docker-compose.yml`, контейнеры `portfolio-next-*`, `3xui-*`, `postgres-provision`. Подробнее — в [INFRA.md](INFRA.md).
- **Шаг — тест — коммит.** Не накапливать коммиты на 5 шагов вперёд.
