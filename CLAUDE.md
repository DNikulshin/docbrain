# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Общение с пользователем — на русском (см. `~/.claude/CLAUDE.md`). Стиль: чёткий, без воды.

## Стадия проекта

Pre-implementation. На 2026-05-13 в репозитории только два документа:
- [README.md](README.md) — продуктовый план, целевая архитектура, целевая структура каталогов, примеры тестов, шаги деплоя.
- [INFRA.md](INFRA.md) — брифинг по VPS (`nikulshin-dev.online`): какие контейнеры уже крутятся, какая docker-сеть, где Caddy/Authelia/MinIO/Postgres, что нужно доставить под docbrain.

Кода, `docker-compose.yml`, `Dockerfile`, миграций, тестов **ещё нет**. Перед любой реализацией свериться с этими двумя файлами — там зафиксированы все принятые решения.

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

> На момент 2026-05-13 ни одна из этих команд ещё не работает — их предстоит создать. Команды приведены как **целевые**, согласно README.md.

Backend (Python 3.11, FastAPI):
- `pip install -r backend/requirements.txt` — установка
- `pytest backend/tests` — все тесты
- `pytest backend/tests/test_rag.py::test_search_similar` — один тест
- `pytest backend/tests --cov=app` — с покрытием (как в CI)
- Миграции: `alembic` в `backend/alembic/`

Frontend (Node 20, Next.js 15):
- `cd frontend && npm ci` — установка
- `cd frontend && npm test` — Jest + React Testing Library
- `cd frontend && npm run dev` — dev-сервер

Стек целиком (на VPS):
- `cd /home/coder/projects/docbrain && docker-compose up -d --build` — поднять backend/web/db/n8n
- `docker logs docbrain-backend -f` / `docker logs docbrain-n8n` — логи

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
- **2026-05-13** — Выбран **вариант 2** из INFRA.md §3: отдельный `docbrain-db` на `pgvector/pgvector:pg16`, чтобы не ломать scan-agent.
- **2026-05-13** — Авторизация веб-чата: **JWT в FastAPI**, не Authelia.
- **2026-05-13** — n8n: **pull-mode** каждые 6ч из Google Drive.
- **2026-05-13** — OpenRouter: **один ключ на сервис** (single-tenant на старте).

## Что сделано

- Описаны архитектура и план реализации (README.md).
- Описана целевая VPS-инфра и интеграция (INFRA.md).

## Что осталось (большие блоки)

- Инициализировать git-репозиторий и каркас (`backend/`, `frontend/`, `n8n/`, `docker-compose.yml`, `.env.example`, `Makefile`).
- Backend: модели, RAG-слой (embedding/vector_store/retriever), function-calling агент, API (chat/documents/import/telegram), парсеры PDF/DOCX/MD/URL, alembic-миграции.
- Frontend: чат, админка, интеграция с API, тесты Jest.
- n8n workflow Google Drive → `/api/import-from-n8n` (JSON в `n8n/workflows/`).
- CI (`.github/workflows/ci.yml`) и CD (`.github/workflows/cd.yml`) по шаблону scan-agent.
- Caddyfile: добавить блоки `docbrain.nikulshin-dev.online` и `n8n.nikulshin-dev.online`.
- Создать MinIO-бакет `docbrain-files`.
- Завести нового Telegram-бота и настроить webhook.

## Нюансы / подводные камни

- **Telegram-webhook должен быть публичным** — без `import authelia` (Telegram не умеет SSO). Только префикс `/tg/webhook*`.
- **pgvector в основном `postgres-provision` не установлен** — поэтому отдельный `docbrain-db`.
- В compose **указывать `name: proxy`** в external-сети нельзя — реальное имя сети `home-codespaces_proxy`.
- Volume mount `./backend:/app` в compose — только для разработки, в production убрать.
- `TELEGRAM_BOT_TOKEN` в `/opt/home-codespaces/.env` уже занят dashboard'ом scan-agent — для docbrain ввести отдельный `DOCBRAIN_TELEGRAM_BOT_TOKEN`.
- Открытые вопросы перечислены в INFRA.md §9 (часть уже закрыта решениями выше; перепроверить при старте реализации).

## Источники истины

- [README.md](README.md) — продуктовый план, целевая структура, примеры тестов, пошаговый деплой.
- [INFRA.md](INFRA.md) — VPS, контейнеры, Caddy, Authelia, MinIO, Postgres, варианты pgvector.
- `~/.claude/CLAUDE.md` — глобальные правила взаимодействия (русский язык, шаблон проектного CLAUDE.md).
