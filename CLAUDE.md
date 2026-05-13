# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Общение с пользователем — на русском (см. `~/.claude/CLAUDE.md`). Стиль: чёткий, без воды.

## Стадия проекта

Активная разработка, спринт 1 (фундамент бэкенда) закрыт 2026-05-13.

Источники истины помимо кода:
- [README.md](README.md) — продуктовый план, целевая архитектура, целевая структура каталогов, шаги деплоя.
- [INFRA.md](INFRA.md) — брифинг по VPS (`nikulshin-dev.online`): контейнеры, docker-сеть, Caddy/Authelia/MinIO/Postgres.

## Цель

DocBrain — RAG-консультант по корпоративной документации:
FastAPI (RAG + function-calling agent) + Next.js 15 (веб-чат и админка) + n8n (синхронизация Google Drive по cron) + PostgreSQL/pgvector + MinIO (исходники файлов) + Telegram-бот.
LLM и эмбеддинги — через **OpenRouter** (один API-ключ на оба).

## Big-picture архитектура (после реализации)

```
Telegram ──webhook──▶ FastAPI (docbrain-backend)
User ──HTTPS──▶ Caddy ──▶ Next.js (docbrain-web)  ─REST─▶ FastAPI
                       └─ /api/* ─▶ FastAPI
                       └─ n8n.* (за Authelia) ─▶ docbrain-n8n ─pull 6h─▶ Google Drive
                                                                     └─POST /api/import─▶ FastAPI
FastAPI ─эмбеддинги─▶ PostgreSQL+pgvector (docbrain-db, отдельный контейнер)
FastAPI ─исходники──▶ MinIO (бакет docbrain-files, существующий инстанс)
```

Ключевые архитектурные решения (источник — INFRA.md и README.md):
- **pgvector в отдельном контейнере** `docbrain-db` (вариант 2 из INFRA.md §3) — изоляция от существующего `postgres-provision`, чтобы не сломать scan-agent.
- **Веб-чат публичный, авторизация JWT на уровне FastAPI** (не Authelia). Telegram-бот идентифицирует пользователей по `chat_id`.
- **n8n за Authelia** — НЕ публичный, snippet `import authelia` в Caddyfile.
- **Telegram webhook без Authelia** — Telegram не умеет SSO, маршрут `/tg/webhook*` отдельным `handle` без `import authelia`.
- **MinIO** — переиспользуем существующий инстанс, бакет `docbrain-files`.
- **n8n импорт документов** — pull-mode каждые 6 часов из Google Drive (см. workflow в README §«Шаг 6»).

## Целевая структура репозитория

См. README.md §«Структура репозитория» — следовать ей при первой реализации:
`backend/` (FastAPI + alembic + tests), `frontend/` (Next.js App Router), `n8n/workflows/`, корневой `docker-compose.yml`, `.env.example`, `Makefile`.

## Команды разработки

Локально pip/python3 в code-server'е недоступны (pip отсутствует, Python 3.13) — **все backend-команды гоняем внутри контейнера**.

Стек:
- `docker-compose up -d --build` — поднять стек (docker-compose V1, V2 не установлен)
- `docker-compose logs -f docbrain-backend` — логи бэкенда
- `docker-compose down` — остановить

Backend (внутри контейнера):
- `docker-compose exec docbrain-backend sh -c "cd /app && pytest -v"` — тесты
- `docker-compose exec docbrain-backend sh -c "cd /app && pytest tests/test_health.py::test_health_returns_ok"` — один тест
- `docker-compose exec docbrain-backend sh -c "cd /app && ruff check . && ruff format --check ."` — линт
- `docker-compose exec docbrain-backend sh -c "cd /app && ruff format ."` — автоформат
- `docker-compose exec docbrain-backend sh -c "cd /app && alembic current"` — текущая ревизия БД
- `docker-compose exec docbrain-backend sh -c "cd /app && alembic revision -m 'msg'"` — новая ручная миграция
- `alembic upgrade head` запускается автоматически при старте контейнера (`docker-entrypoint.sh`)

Проверка endpoint'ов (backend в proxy-сети, порт наружу не выставлен):
- `docker run --rm --network home-codespaces_proxy curlimages/curl:latest -s http://docbrain-backend:8000/health`
- `docker run --rm --network home-codespaces_proxy curlimages/curl:latest -s http://docbrain-backend:8000/health/db`

Postgres напрямую:
- `docker exec docbrain-db psql -U docbrain -d docbrain -c "..."`

Frontend (будет позже): `cd frontend && npm ci && npm run dev`.

Caddy после правки `/opt/home-codespaces/Caddyfile`:
- `docker exec home-codespaces-caddy-1 caddy reload --config /etc/caddy/Caddyfile`

## Окружение и интеграция с VPS

Работа идёт **внутри code-server-контейнера** на VPS, но `/var/run/docker.sock` примонтирован — доступны `docker ps/exec/inspect` любых контейнеров VPS.

- Все сервисы docbrain цепляются к **внешней docker-сети** `home-codespaces_proxy` (она же `proxy`). Объявлять её как `external: true, name: home-codespaces_proxy`.
- Compose-проект docbrain — **отдельный** `/home/coder/projects/docbrain/docker-compose.yml`, не править корневой `/opt/home-codespaces/docker-compose.yml`.
- `.env` для деплоя лежит в `/opt/home-codespaces/projects/docbrain/.env` (на хосте); шаблон — в `.env.example` (создать).
- Секреты в `/opt/home-codespaces/.env` (общие): `MINIO_*`, `TELEGRAM_BOT_TOKEN` (этот — чужого бота, для docbrain создать **новый**), `DB_PROVISIONER_API_SECRET`. **Никогда не печатать значения в чат.**
- CI/CD: GHA → GHCR (`ghcr.io/dnikulshin/docbrain/{backend,web}`) → webhook на VPS (`https://webhook.nikulshin-dev.online/hooks/deploy-docbrain`) → `compose pull && up -d`.

## Что НЕ трогать

- Контейнеры и тома `portfolio-next-*` и `3xui-*` — чужие, к docbrain отношения не имеют.
- Существующий `postgres-provision` (используется scan-agent) — не подменять образ; для docbrain поднимаем отдельный `docbrain-db` на `pgvector/pgvector:pg16`.
- Корневой `/opt/home-codespaces/docker-compose.yml` без явного запроса.

## Принятые решения (с датами)

- **2026-05-13** — Зафиксирована целевая архитектура и стек (см. README.md, INFRA.md).
- **2026-05-13** — Выбран **вариант 2** из INFRA.md §3: отдельный `docbrain-db` на `pgvector/pgvector:pg16` — БД, созданная ранее в `postgres-provision`, не используется (pgvector там недоступен, см. нюанс ниже).
- **2026-05-13** — Авторизация веб-чата: **JWT в FastAPI**, не Authelia.
- **2026-05-13** — n8n: **pull-mode** каждые 6ч из Google Drive.
- **2026-05-13** — OpenRouter: **один ключ на сервис** (single-tenant на старте).
- **2026-05-13** — Conventional Commits, ruff (lint+format) как единый линтер Python.
- **2026-05-13** — SQLAlchemy 2.x async + asyncpg, alembic в async-режиме (target_metadata=None, миграции пишем вручную пока нет моделей).
- **2026-05-13** — Миграции применяются автоматически в `docker-entrypoint.sh` (alembic upgrade head перед uvicorn).

## Что сделано

- Спринт 1 (фундамент бэкенда):
  - git-репозиторий, `.gitignore` (с защитой `.env`), Conventional Commits.
  - `docker-compose.yml`: docbrain-db (pgvector/pgvector:pg16) + docbrain-backend, общая сеть `home-codespaces_proxy`.
  - FastAPI 0.115 / Python 3.11 в Docker (dev + prod targets, --reload в dev).
  - `GET /health` (только сервис) и `GET /health/db` (SELECT 1 + версия pgvector).
  - SQLAlchemy async + asyncpg + alembic; baseline-миграция `0001_enable_pgvector` (CREATE EXTENSION vector → 0.8.2).
  - 3 теста (pytest + dependency_overrides), ruff (E/W/F/I/B/UP/ASYNC/SIM).

## Что осталось (большие блоки)

- Эмбеддинги через OpenRouter (нужен `OPENROUTER_API_KEY` в .env), модель документов и чанков в БД (`documents`/`chunks` с `vector(N)`), retrieval + cosine, function-calling агент.
- API: `/api/chat`, `/api/documents`, `/api/import`, `/tg/webhook`.
- Парсеры PDF/DOCX/MD/URL, загрузка исходников в MinIO.
- Frontend: Next.js 15, чат + админка, тесты Jest.
- n8n workflow Google Drive → `/api/import`.
- CI (`.github/workflows/ci.yml`) и CD через GHCR + webhook.
- Caddyfile: блоки `docbrain.nikulshin-dev.online` и `n8n.nikulshin-dev.online`.
- MinIO-бакет `docbrain-files`, новый Telegram-бот и его webhook.

## Нюансы / подводные камни

- **`BACKEND_HOST_PATH` в .env** — обязателен на VPS code-server. docker-daemon живёт на хосте, и относительный `./backend` в compose резолвится как путь хоста, а не code-server'а. Реальное значение: `/opt/home-codespaces/projects/docbrain/backend`. На чистом dev-окружении переменную не задавать — compose возьмёт fallback `./backend`.
- **`docker compose` (V2) не установлен** в code-server — использовать `docker-compose` (V1).
- **`python3` есть, `pip` нет** в code-server — все Python-команды гонять только в контейнере.
- **Bind-mount затирает executable-бит** из слоя образа. Поэтому `ENTRYPOINT ["sh", "./docker-entrypoint.sh"]` — не зависит от `chmod +x`.
- **Telegram-webhook должен быть публичным** — без `import authelia` (Telegram не умеет SSO). Только префикс `/tg/webhook*`.
- **pgvector в основном `postgres-provision` не установлен** (`postgres:16-alpine`) — поэтому отдельный `docbrain-db`.
- В compose external-сеть пишется как `name: home-codespaces_proxy`, не `name: proxy`.
- `TELEGRAM_BOT_TOKEN` в `/opt/home-codespaces/.env` уже занят dashboard'ом scan-agent — для docbrain ввести отдельный `DOCBRAIN_TELEGRAM_BOT_TOKEN`.
- `Settings.database_url` обязателен → юнит-тесты подставляют фейк через `tests/conftest.py` (`os.environ.setdefault` до импортов app).
- Старый `.env`, который указывал на `postgres-provision/db_docbrain`, сохранён в `.env.old.bak` (gitignored). Сама БД `db_docbrain` в `postgres-provision` осталась пустой — можно безопасно удалить через db-provisioner UI.

## Источники истины

- [README.md](README.md) — продуктовый план, целевая структура, примеры тестов, пошаговый деплой.
- [INFRA.md](INFRA.md) — VPS, контейнеры, Caddy, Authelia, MinIO, Postgres, варианты pgvector.
- `~/.claude/CLAUDE.md` — глобальные правила взаимодействия (русский язык, шаблон проектного CLAUDE.md).
