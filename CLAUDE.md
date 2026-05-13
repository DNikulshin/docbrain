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

Спринт 1 закрыт (2026-05-13). `docker-compose up -d --build` поднимает `docbrain-db` (PG16 + pgvector 0.8.2) и `docbrain-backend` (FastAPI 0.115). Эндпоинты `/health` и `/health/db` отвечают, alembic применил `0001_enable_pgvector`. Команды — в [docs/dev.md](docs/dev.md).

## Стиль работы

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`). Основная ветка — `main`, remote `github.com/DNikulshin/docbrain`.
- **Перед коммитом** обязательно: `ruff check .`, `ruff format --check .`, `pytest -v` — все внутри контейнера (см. [docs/dev.md](docs/dev.md)).
- **Не трогать** `.env` (живые пароли, gitignored), корневой `/opt/home-codespaces/docker-compose.yml`, контейнеры `portfolio-next-*`, `3xui-*`, `postgres-provision`. Подробнее — в [INFRA.md](INFRA.md).
- **Шаг — тест — коммит.** Не накапливать коммиты на 5 шагов вперёд.
