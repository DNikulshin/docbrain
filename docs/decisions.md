# Архитектурные решения

Журнал принятых решений с датами. Новые записи — сверху.

## 2026-05-18 — Спринт 3 закрыт: парсеры PDF/DOCX/URL

- **`pypdf` / `python-docx` / `trafilatura`** — три отдельных парсера. `parse_pdf` и `parse_docx` принимают `bytes`, возвращают `str`. `parse_url(url, http, max_bytes)` — async, стриминговый GET с лимитом размера, диспатч по `Content-Type` (html → trafilatura, pdf → `parse_pdf`, docx → `parse_docx`, text/plain → utf-8 decode).
- **`POST /api/documents/url`** — новый эндпоинт, body `{"url": "HttpUrl"}`. Оригинал льётся в MinIO под ключом `url/{document_id}/{filename}`, `Document.source = "s3://docbrain-files/url/{doc_id}/{filename}"`. Та же цепочка: parse → chunk → embed → write.
- **Маршрут `/url` зарегистрирован до `/{document_id}`** в роутере — иначе FastAPI матчит строку `"url"` как UUID-параметр и отдаёт 422.
- **Маркер `integration`** добавлен в `pyproject.toml` (`markers = ["integration: ..."]`); MinIO-тесты скипаются без `MINIO_ACCESS_KEY`.
- **111 тестов, 5 skipped** (MinIO integration без ключа) — `ruff check . && pytest -v` зелёные внутри `docbrain-backend`.

## 2026-05-18 — Спринт 3, шаг 3.4: MinIO

- **`aiobotocore[boto3]`** как async S3-клиент. Нативный async без `asyncio.to_thread`.
- **Два клиента в `lifespan`:** `client` на `MINIO_ENDPOINT` (internal, для put/head/delete/health), `pub_client` на `MINIO_PUBLIC_ENDPOINT` (для `generate_presigned_url` — чтобы URL был публичным). Оба создаются через `AsyncExitStack`-подобный вложенный `async with`.
- **`generate_presigned_url` — синхронный метод** (`def`, не `async def`). В aiobotocore это HMAC-подпись без сетевого вызова. `StorageProtocol` и все реализации (`MinioStorage`, `StubStorage`) определяют его как `def`.
- **`Document.source = "s3://docbrain-files/{doc_id}/{filename}"`**. `doc_id` генерируется ДО `put_object`, чтобы использовать в ключе S3. Если MinIO не настроен — `source` остаётся `NULL`, приложение стартует без ошибок.
- **`GET /api/documents/{id}/source` → 302** на presigned URL. Если `source is None` или документ не найден → 404; если storage не сконфигурирован → 503.
- **`DELETE /api/documents/{id}` удаляет объект из MinIO best-effort:** после удаления строки из БД, ошибка S3 → `logger.warning`, не исключение.
- **`StubStorage` (in-memory dict) в `dependency_overrides`** для всех API-тестов — MinIO не нужен при `pytest`. Integration-тесты (`tests/storage/test_minio.py`, `@pytest.mark.integration`) создают временный бакет и скипаются без `MINIO_ACCESS_KEY`.
- **`/health/minio`** — `HeadBucket` через внутренний клиент; возвращает `{"status": "not_configured"}` если MinIO не задан.

## 2026-05-18 — Спринт 3, шаги 3.1–3.3: логирование, ошибки, OpenRouter

- **`structlog` + request_id middleware (3.1).** `configure_logging()` собирает процессоры; `LOG_FORMAT=json` → `JSONRenderer`, иначе `ConsoleRenderer`. `RequestContextMiddleware` генерит UUID4 `request_id`, биндит в `structlog.contextvars`, возвращает в `X-Request-ID`. Catch-all exception handler перенесён в middleware (а не в `@app.exception_handler(Exception)`) — потому что Starlette 0.41+ ищет handler по точному типу, подклассы не ловит.
- **Глобальные exception-handlers (3.2).** `UnsupportedFormatError` → 415, `ValueError` → 400, `UnicodeDecodeError` → 400; catch-all в middleware → 500 с `request_id` в теле.
- **`OpenRouterEmbeddingService` (3.3).** `httpx.AsyncClient`, батчи по `EMBEDDING_BATCH_SIZE=96`, экспоненциальный backoff `0.5 * 2^attempt` на 5xx/429, до `OPENROUTER_RETRIES=2` ретраев. Несовпадение размерности ответа → `EmbeddingProviderError`. Фабрика `get_embedding_service()` делает fast-fail с `RuntimeError` если `OPENROUTER_API_KEY=None`. Transport инжектируется через `_transport` в конструкторе — для тестов без сети (mock через `httpx.AsyncBaseTransport`).

## 2026-05-14 — Спринт 2 закрыт: data-flow без LLM

- **Stub-first выбран, OpenRouter — спринт 3.** Хотя `OPENROUTER_API_KEY` доступен (см. запись от 2026-05-13), пошли stub-first: детерминированный `StubEmbeddingService` упрощает интеграционные тесты, заменяется на реальный клиент одним коммитом без правки клиентов (за это отвечает `EmbeddingService` Protocol + фабрика `get_embedding_service()` по `settings.embedding_provider`).
- **`EMBEDDING_DIM=1536` зафиксирован в миграции `0002`.** Изменение размерности — только новой миграцией: pgvector не умеет ALTER `vector(N)` без пересоздания индекса.
- **Метрика — cosine** (`vector_cosine_ops`, оператор `<=>`), HNSW-индекс на `chunks.embedding`. Параметры HNSW — дефолтные pgvector 0.8.2.
- **Hard delete документов** (`ON DELETE CASCADE` на `chunks.document_id`). Soft delete отложен до появления пользовательских ролей.
- **Только текст в БД.** Оригинал файла (bytes) не сохраняется, `Document.source` пока `NULL`. MinIO + `source = s3://...` — спринт 3.
- **Лимит загрузки 10 МБ** (`settings.max_upload_bytes`), нарушение → 413. Неизвестное расширение → 415 (`UnsupportedFormatError`).
- **`ChunkRead` без поля `embedding`.** Векторы не отдаём наружу: не нужны клиенту, раздувают payload, потенциальная утечка эмбеддинг-модели.
- **Тестовая инфра — rollback-фикстура на живом `docbrain-db`:** внешняя транзакция + `join_transaction_mode="create_savepoint"`, отдельный engine с `NullPool` (иначе под pytest-asyncio ловим «event loop is closed»). Юниты — на чистую логику (chunker, парсеры, stub-embeddings).
- **API-тесты — `httpx.AsyncClient` + `ASGITransport`, не `TestClient`.** `TestClient` крутит свой event loop, несовместимый с async-фикстурой rollback'а. Общая `db_session` живёт в `backend/tests/conftest.py`, чтобы её видели и `tests/api/`, и `tests/services/`.
- **`POST /api/search` валидация:** `query` `min_length=1`, `top_k ∈ [1, 50]`. На stub-эмбеддингах query=text чанка даёт `distance≈0` — поиск детерминирован в тестах.

## 2026-05-13 — Готовность к спринту 2

- **`OPENROUTER_API_KEY` доступен в `.env`** (положил пользователь после закрытия спринта 1). Это снимает блокер для реального RAG.
- **Развилка спринта 2 — stub-first vs real-first.** План в [sprint-2-plan.md](sprint-2-plan.md) написан на stub-first (детерминированный `StubEmbeddingService` для тестов, потом OpenRouter). Раз ключ есть, новая сессия может пойти real-first и сразу делать OpenRouter-клиент в Шаге 2.3. Решение принимается в начале новой сессии, оба пути валидны.
- **`.env.example` приведён в актуальное состояние** для спринта 2: добавлены `OPENROUTER_API_KEY`, `EMBEDDING_MODEL`, `CHAT_MODEL`, `EMBEDDING_PROVIDER`, `EMBEDDING_DIM`, `CHUNK_SIZE`, `CHUNK_OVERLAP`.

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
