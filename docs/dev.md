# Разработка

## Окружение

Разработка идёт **внутри code-server-контейнера на VPS**. `docker.sock` хоста проброшен, поэтому docker-команды управляют контейнерами хоста. Особенности:

- `python3` есть (3.13), но **pip нет** — все Python-команды только в контейнере backend.
- **`docker compose` (V2) не установлен** — используем `docker-compose` (V1).
- Относительный путь `./backend` в `docker-compose.yml` резолвится docker-daemon'ом **на хосте**, а не внутри code-server. Поэтому в `.env` обязателен `BACKEND_HOST_PATH=/opt/home-codespaces/projects/docbrain/backend` (полный путь как видит хост-FS). На чистом dev-окружении переменную не задавать — `compose` возьмёт fallback `./backend`.
- **Bind-mount затирает executable-бит** слоя образа → entrypoint объявлен как `ENTRYPOINT ["sh", "./docker-entrypoint.sh"]`.

## Быстрый старт

```bash
cp .env.example .env
# отредактировать .env: POSTGRES_PASSWORD, DATABASE_URL, BACKEND_HOST_PATH
docker-compose up -d --build
```

Проверка:

```bash
docker run --rm --network home-codespaces_proxy curlimages/curl:latest -s \
  http://docbrain-backend:8000/health/db
# ожидаем: {"status":"ok","db":"ok","pgvector":"0.8.2"}
```

## Команды

### Стек

| Действие | Команда |
|---|---|
| Поднять | `docker-compose up -d --build` |
| Перезапустить backend | `docker-compose up -d --build docbrain-backend` |
| Логи backend | `docker-compose logs -f docbrain-backend` |
| Остановить | `docker-compose down` |
| Снести с volume | `docker-compose down -v` *(удаляет данные БД)* |

### Backend (внутри контейнера)

```bash
# Тесты
docker-compose exec docbrain-backend sh -c "cd /app && pytest -v"
docker-compose exec docbrain-backend sh -c "cd /app && pytest tests/test_health.py::test_health_returns_ok"

# Линт и формат
docker-compose exec docbrain-backend sh -c "cd /app && ruff check ."
docker-compose exec docbrain-backend sh -c "cd /app && ruff format --check ."
docker-compose exec docbrain-backend sh -c "cd /app && ruff format . && ruff check --fix ."

# Alembic
docker-compose exec docbrain-backend sh -c "cd /app && alembic current"
docker-compose exec docbrain-backend sh -c "cd /app && alembic history"
docker-compose exec docbrain-backend sh -c "cd /app && alembic revision -m 'message'"
docker-compose exec docbrain-backend sh -c "cd /app && alembic upgrade head"
docker-compose exec docbrain-backend sh -c "cd /app && alembic downgrade -1"
```

### Прямой доступ к БД

```bash
docker exec -it docbrain-db psql -U docbrain -d docbrain
```

### Проверка endpoint'ов

Backend в сети `home-codespaces_proxy`, порт наружу не выставлен. Из code-server:

```bash
docker run --rm --network home-codespaces_proxy curlimages/curl:latest -s \
  http://docbrain-backend:8000/health
```

## Перед коммитом

1. `ruff check .` — 0 ошибок.
2. `ruff format --check .` — все файлы отформатированы.
3. `pytest -v` — все тесты зелёные.
4. Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`, `perf:`. Scope опционален (`feat(backend): ...`).

## Что НЕ трогать

- Корневой `/opt/home-codespaces/docker-compose.yml` без явного запроса.
- Контейнеры `portfolio-next-*`, `3xui-*` — чужие.
- `postgres-provision` — используется scan-agent, не подменять образ.
- Файл `.env` — содержит реальные пароли. Любые правки — с согласия пользователя.

## FAQ

**Почему `BACKEND_HOST_PATH`?** docker-daemon живёт на хосте VPS, а code-server — внутри контейнера. Относительный путь в compose резолвится daemon'ом → файлы ищутся на хост-FS, а там путь другой. Подробности в [decisions.md](decisions.md).

**Где хранятся данные БД?** В docker-volume `docbrain_pgdata_docbrain` (на хосте `/var/lib/docker/volumes/...`). Удалить можно через `docker-compose down -v`.

**Как добавить миграцию?** `docker-compose exec docbrain-backend sh -c "cd /app && alembic revision -m 'add documents table'"` → отредактировать `backend/alembic/versions/*.py` → перезапустить backend (миграции применятся автоматически).

**Тесты падают с `ValidationError: DATABASE_URL`?** Проверь, что `tests/conftest.py` импортируется (`os.environ.setdefault` подставляет фейковый URL до импорта `app.*`).
