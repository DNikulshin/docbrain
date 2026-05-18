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
- [docs/sprint-3-plan.md](docs/sprint-3-plan.md) — текущий спринт. История спринта 2 — в [docs/sprint-2-plan.md](docs/sprint-2-plan.md).

## Что сейчас работает

Спринт 1 закрыт (2026-05-13). `docker-compose up -d --build` поднимает `docbrain-db` (PG16 + pgvector 0.8.2) и `docbrain-backend` (FastAPI 0.115). Эндпоинты `/health` и `/health/db` отвечают.

Спринт 2 закрыт (2026-05-14). `POST /api/documents` (multipart, TXT/MD, лимит 10 МБ) парсит → чанкует → эмбеддит (stub) → пишет `Document` + `Chunk`-и в одной транзакции; `GET/DELETE /api/documents[/{id}]` для CRUD. `POST /api/search` — top-k по cosine через HNSW. 77 тестов зелёные (unit + integration на живой БД + API через `httpx.AsyncClient + ASGITransport`).

Спринт 3 в процессе — [docs/sprint-3-plan.md](docs/sprint-3-plan.md). Шаги 3.1–3.3 закрыты (2026-05-18): structlog + request_id middleware, глобальные exception-handlers (`ValueError`/`UnicodeDecodeError` → 400), реальный `OpenRouterEmbeddingService` с batch+retry. 89 тестов зелёные. Следующий — шаг 3.4: MinIO (`aiobotocore`, бакет `docbrain-files`). Без n8n, фронта, Telegram, CI/CD. Архитектурные решения — в [docs/decisions.md](docs/decisions.md). Команды — в [docs/dev.md](docs/dev.md).

## Стиль работы

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`). Основная ветка — `main`, remote `github.com/DNikulshin/docbrain`.
- **Перед коммитом** обязательно: `ruff check .`, `ruff format --check .`, `pytest -v` — все внутри контейнера (см. [docs/dev.md](docs/dev.md)).
- **Не трогать** `.env` (живые пароли, gitignored), корневой `/opt/home-codespaces/docker-compose.yml`, контейнеры `portfolio-next-*`, `3xui-*`, `postgres-provision`. Подробнее — в [INFRA.md](INFRA.md).
- **Шаг — тест — коммит.** Не накапливать коммиты на 5 шагов вперёд.
