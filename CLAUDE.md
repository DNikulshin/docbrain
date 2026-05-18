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
- [docs/sprint-4-plan.md](docs/sprint-4-plan.md) — история спринта 4 (закрыт). История спринтов 2–3 — в [docs/sprint-3-plan.md](docs/sprint-3-plan.md), [docs/sprint-2-plan.md](docs/sprint-2-plan.md).

## Что сейчас работает

Спринт 1 закрыт (2026-05-13). `docker-compose up -d --build` поднимает `docbrain-db` (PG16 + pgvector 0.8.2) и `docbrain-backend` (FastAPI 0.115). Эндпоинты `/health` и `/health/db` отвечают.

Спринт 2 закрыт (2026-05-14). `POST /api/documents` (multipart, TXT/MD, лимит 10 МБ) парсит → чанкует → эмбеддит (stub) → пишет `Document` + `Chunk`-и в одной транзакции; `GET/DELETE /api/documents[/{id}]` для CRUD. `POST /api/search` — top-k по cosine через HNSW. 77 тестов зелёные (unit + integration на живой БД + API через `httpx.AsyncClient + ASGITransport`).

Спринт 3 закрыт (2026-05-18) — [docs/sprint-3-plan.md](docs/sprint-3-plan.md). Шаги 3.1–3.5: structlog + request_id middleware, глобальные exception-handlers (`ValueError`/`UnicodeDecodeError` → 400, `UnsupportedFormatError` → 415), реальный `OpenRouterEmbeddingService` с batch+retry, MinIO (`aiobotocore`, `StorageProtocol`/`MinioStorage`/`StubStorage`, lifespan, `Document.source`, `GET /api/documents/{id}/source` → 302, `/health/minio`), парсеры PDF/DOCX/URL + `POST /api/documents/url` (оригинал в MinIO). 111 тестов зелёные (5 skipped — MinIO integration).

Спринт 4 закрыт (2026-05-18) — [docs/sprint-4-plan.md](docs/sprint-4-plan.md). Шаги 4.1–4.5: `X-API-Key` auth для `/api/import/*` (`DOCBRAIN_API_KEY`, dev mode без ключа), `source_id` в Document (миграция `0003`), `POST /api/import/gdrive` (multipart, replace semantics, `GdriveImportRead`), `docbrain-n8n` контейнер в docker-compose, n8n workflow JSON (`n8n/gdrive-import.json`, schedule 6h, Google Drive → filter MIME → download → POST backend). 116 тестов зелёные (5 skipped — MinIO integration). Следующий — спринт 5. Архитектурные решения — в [docs/decisions.md](docs/decisions.md). Команды — в [docs/dev.md](docs/dev.md).

## Стиль работы

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`). Основная ветка — `main`, remote `github.com/DNikulshin/docbrain`.
- **Перед коммитом** обязательно: `ruff check .`, `ruff format --check .`, `pytest -v` — все внутри контейнера (см. [docs/dev.md](docs/dev.md)).
- **Не трогать** `.env` (живые пароли, gitignored), корневой `/opt/home-codespaces/docker-compose.yml`, контейнеры `portfolio-next-*`, `3xui-*`, `postgres-provision`. Подробнее — в [INFRA.md](INFRA.md).
- **Шаг — тест — коммит.** Не накапливать коммиты на 5 шагов вперёд.
