# Спринт 3: production-ready RAG (логирование, ошибки, OpenRouter, MinIO, парсеры)

## Цель

Превратить stub-пайплайн спринта 2 в production-ready backend: появятся **реальные эмбеддинги** (OpenRouter), **сохранение оригиналов** (MinIO), **дополнительные парсеры** (PDF/DOCX/URL), **структурированное логирование** и **корректные коды ошибок** в API. Фронт, n8n, Telegram, Authelia, CI/CD — отдельные спринты.

К концу спринта `EMBEDDING_PROVIDER=openrouter` поднимает приложение и реально эмбеддит документы; `POST /api/documents` кладёт оригинал в MinIO и пишет `Document.source = "s3://docbrain-files/{key}"`; `POST /api/documents/url` принимает URL и индексирует страницу/файл по сети; PDF и DOCX поддерживаются; в логах структурированный JSON с `request_id`; ошибки парсинга/валидации не возвращают 500.

## Решения, принятые на старте спринта (2026-05-14)

- **Объём — M (бэкенд-фокус).** Логирование + хендлеры ошибок + OpenRouter + MinIO + PDF/DOCX/URL. Без CI/CD, n8n, фронта, Telegram, очередей.
- **Логирование — `structlog`** (JSON в prod, ConsoleRenderer в dev по `LOG_FORMAT`) + middleware с `request_id` (UUID4), bind в `structlog.contextvars`, эхо в `X-Request-ID` ответа.
- **MinIO-клиент — `aiobotocore`** (нативный async, без `asyncio.to_thread`). Endpoint **внутренний** — имя контейнера `home-codespaces-minio-1:9000` (мы уже подключены к сети `home-codespaces_proxy` через external network в [docker-compose.yml](../docker-compose.yml)). Публичный `s3.nikulshin-dev.ru` оставляем для presigned URL.
- **`Document.source`** хранит S3-URI вида `s3://docbrain-files/{document_id}/{filename}` (или `s3://docbrain-files/url/{document_id}` для URL). Presigned URL генерим on-demand через `GET /api/documents/{id}/source` → 302.
- **OpenRouter** — `httpx.AsyncClient` с `timeout`, ретраи на 5xx/429 с экспоненциальным backoff (наша обвязка, без `tenacity`). Батчи по `EMBEDDING_BATCH_SIZE` (дефолт 96 — безопасно ниже openai-лимита 100 на запрос).
- **Парсер URL** — отдельный эндпоинт `POST /api/documents/url` (тело `{url}`): GET через `httpx.AsyncClient` → по `Content-Type` диспатч (`text/html` → `trafilatura.extract`, `application/pdf` → `pypdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` → `python-docx`, `text/plain` → как есть). Лимит размера ответа — тот же `MAX_UPLOAD_BYTES`.
- **ANALITICS.md** — после переноса выводов в этот план **удаляется**. Пункт 2.4 из аналитики (тесты зависят от `.env`) признан некорректным: embedder в тестах инжектится напрямую, фабрика читается только в API-роутерах, которые покрыты через `dependency_overrides`.

## Источники истины

- [decisions.md](decisions.md) — фактические решения спринта 2 (2026-05-14) + добавим спринта 3 по ходу.
- [../INFRA.md](../INFRA.md) — MinIO уже на VPS (`home-codespaces-minio-1`), бакет создаём `docbrain-files`.
- [../README.md](../README.md) §«Шаг 1. Создание бакета в MinIO» — команды `mc mb local/docbrain-files`.
- pgvector / OpenRouter docs (`/api/v1/embeddings`).

## Статус спринта

- [x] **Шаг 3.1** — структурированное логирование (`structlog` + middleware request_id).
- [ ] **Шаг 3.2** — глобальные exception-handlers, маппинг `ValueError`/`UnicodeDecodeError` → 400.
- [ ] **Шаг 3.3** — реальный `OpenRouterEmbeddingService` + batch + retry.
- [ ] **Шаг 3.4** — интеграция с MinIO, `Document.source`, `GET /api/documents/{id}/source`, `/health/minio`.
- [ ] **Шаг 3.5** — парсеры PDF, DOCX, URL + `POST /api/documents/url`.
- [ ] **Шаг 3.6** — wrap up (decisions.md, CLAUDE.md, статус).

---

## Шаги

### Шаг 3.1 — Логирование (`structlog` + request_id)

- Зависимость `structlog` в [backend/requirements.txt](../backend/requirements.txt).
- Новый модуль `backend/app/logging_config.py`:
  - `configure_logging()` — собирает процессоры (`add_log_level`, `TimeStamper(fmt="iso")`, `merge_contextvars`, exception/stack). Renderer — `JSONRenderer()` если `settings.log_format == "json"`, иначе `ConsoleRenderer()`. Stdlib `logging` тоже подключаем через `structlog.stdlib.ProcessorFormatter` (чтобы логи uvicorn/SQLAlchemy шли в общий формат).
- В `backend/app/config.py` — поля `log_level: str = "INFO"`, `log_format: Literal["console", "json"] = "console"`.
- В [backend/app/main.py](../backend/app/main.py) — вызов `configure_logging()` до `FastAPI(...)`, регистрация middleware `RequestContextMiddleware`.
- Новый файл `backend/app/middleware/request_context.py`:
  - `RequestContextMiddleware(BaseHTTPMiddleware)`: на каждый запрос — `request_id = request.headers.get("X-Request-ID") or uuid4().hex`, `structlog.contextvars.bind_contextvars(request_id=request_id, path=..., method=...)`, в `finally` — `clear_contextvars()`. В ответ добавляет `X-Request-ID`.
- Минимальные логи в коде:
  - `app/services/documents.py` — `logger.info("document_create_start", filename=..., size=...)`, `logger.info("document_create_done", document_id=..., chunks=...)`.
  - `app/services/search.py` — `logger.info("search_query", top_k=..., query_len=...)`, `logger.info("search_done", hits=..., latency_ms=...)`.
- Тесты:
  - `tests/test_logging_middleware.py`: middleware ставит уникальный `X-Request-ID` если в запросе его нет; пробрасывает входящий, если есть; structlog видит этот id в `contextvars` (через `structlog.testing.LogCapture`).

**Файлы:** `backend/requirements.txt`, `backend/app/logging_config.py`, `backend/app/middleware/__init__.py`, `backend/app/middleware/request_context.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/app/services/*.py`, `backend/tests/test_logging_middleware.py`, `.env.example` (`LOG_FORMAT`, `LOG_LEVEL`).

**Коммит:** `feat(backend): structlog + request_id middleware`.

### Шаг 3.2 — Глобальные exception-handlers

- В `backend/app/main.py`:
  - `@app.exception_handler(UnsupportedFormatError)` → 415, `{"detail": str(exc)}`. Удалить локальный try/except в роутере [backend/app/api/documents.py](../backend/app/api/documents.py).
  - `@app.exception_handler(ValueError)` → 400. (Сюда упадёт `chunker.split_text` при кривой конфигурации — это сигнал багу, но клиенту лучше 400, чем 500.)
  - `@app.exception_handler(UnicodeDecodeError)` → 400 — на случай если парсер TXT не справился (сейчас `parse_text` использует `errors="replace"`, но защищаемся на будущее).
  - `@app.exception_handler(Exception)` (catch-all) → 500 с логированием `logger.exception("unhandled_exception", ...)`. Тело — `{"detail": "Internal Server Error", "request_id": <id из contextvars>}` (чтобы можно было искать в логах).
- Все handlers логируют через `structlog` с уровнем `warning` (4xx) или `error` (5xx).
- Тесты:
  - `tests/api/test_error_handlers.py`: подсунуть документ с моком парсера, который кидает `ValueError` → 400 с понятным `detail`. Catch-all через подмену сервиса на мок, кидающий `RuntimeError` → 500 + `request_id` в теле.

**Файлы:** `backend/app/main.py`, `backend/app/api/documents.py` (упростить — убрать локальный try/except), `backend/tests/api/test_error_handlers.py`.

**Коммит:** `feat(backend): глобальные exception-handlers + маппинг 400/415/500`.

### Шаг 3.3 — Реальный `OpenRouterEmbeddingService`

- В [backend/app/config.py](../backend/app/config.py) — добавить поля:
  - `openrouter_api_key: str | None = None`
  - `openrouter_base_url: str = "https://openrouter.ai/api/v1"`
  - `openrouter_embedding_model: str = "openai/text-embedding-3-small"` (синоним к существующему `embedding_model` — переименовать или заоверрайдить).
  - `openrouter_timeout: float = 30.0`
  - `openrouter_retries: int = 2`
  - `embedding_batch_size: int = 96`
- В [backend/app/rag/embeddings.py](../backend/app/rag/embeddings.py):
  - `OpenRouterEmbeddingService(api_key, base_url, model, timeout, retries, batch_size)` (зависимости через конструктор, без сайд-эффектов в импорте).
  - `async def embed(texts)`:
    1. разрезать на батчи по `batch_size`;
    2. POST `{base_url}/embeddings` body `{"model": ..., "input": batch}`, headers `Authorization: Bearer {api_key}`, `HTTP-Referer: https://docbrain.nikulshin-dev.online`;
    3. на 5xx/429 — экспоненциальный backoff `0.5 * 2**i` сек до `retries` попыток;
    4. вернуть `[item["embedding"] for item in resp["data"]]`, склеив порядок батчей.
  - Логи: `logger.info("embedding_request", batch=..., texts=...)`, `logger.warning("embedding_retry", attempt=..., status=...)`.
  - `get_embedding_service()` — если `embedding_provider == "openrouter"` и `openrouter_api_key` None → `RuntimeError` с понятным сообщением (фейлим fast на старте).
- Тесты:
  - `tests/test_openrouter_embeddings.py` через `httpx.MockTransport`:
    - happy path: один батч, два батча, порядок сохраняется;
    - 503 → retry → 200;
    - 5 раз 503 → исключение `EmbeddingProviderError`;
    - размерность ответа фильтруется/валидируется (если приходит не `embedding_dim` — fail).
  - `tests/test_embeddings.py` — обновить тест фабрики: `provider=openrouter` без ключа → `RuntimeError`.

**Файлы:** `backend/app/config.py`, `backend/app/rag/embeddings.py`, `backend/tests/test_openrouter_embeddings.py`, `backend/tests/test_embeddings.py`, `.env.example` (комментарии к новым полям).

**Коммит:** `feat(backend): реальный OpenRouterEmbeddingService с batch + retry`.

### Шаг 3.4 — MinIO интеграция

**Preflight (вручную, до кода — отметить в issue/PR):**

```bash
docker exec home-codespaces-minio-1 mc mb local/docbrain-files
# Заполнить в .env:
# MINIO_ENDPOINT=http://home-codespaces-minio-1:9000
# MINIO_PUBLIC_ENDPOINT=https://s3.nikulshin-dev.ru
# MINIO_ACCESS_KEY=...
# MINIO_SECRET_KEY=...
# MINIO_BUCKET=docbrain-files
```

- Зависимость `aiobotocore` в [backend/requirements.txt](../backend/requirements.txt).
- В [backend/app/config.py](../backend/app/config.py) — поля `minio_endpoint`, `minio_public_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_bucket = "docbrain-files"`, `minio_presign_ttl_sec = 3600`.
- Новый модуль `backend/app/storage/minio.py`:
  - `class MinioStorage` с методами `put_object(key, data, content_type)`, `head_object(key)`, `generate_presigned_url(key)` (использует `minio_public_endpoint` для подписи, чтобы ссылка работала наружу), `health()` (HeadBucket).
  - Внутри — `aiobotocore.session.get_session().create_client("s3", endpoint_url=minio_endpoint, ...)` — оборачиваем в `@asynccontextmanager` или храним long-lived через `lifespan`.
- В [backend/app/services/documents.py](../backend/app/services/documents.py):
  - `create_document` принимает дополнительно `storage: MinioStorage`. Сначала `await storage.put_object(key, payload, content_type)`, затем INSERT с `source=f"s3://{bucket}/{key}"`. На исключении из MinIO — НЕ INSERT'им (документ не появится).
  - `delete_document` дополнительно удаляет объект из MinIO (best effort; если объекта нет — лог warning, не падаем).
- В [backend/app/api/deps.py](../backend/app/api/deps.py) — `StorageDep` (`Annotated[MinioStorage, Depends(get_storage)]`), `get_storage()` берёт `lifespan`-ный клиент из `app.state`.
- В [backend/app/main.py](../backend/app/main.py) — `lifespan` создаёт/закрывает MinIO-клиента, валидирует доступность бакета.
- В [backend/app/api/documents.py](../backend/app/api/documents.py) — `POST /api/documents` использует `StorageDep`. Новый эндпоинт `GET /api/documents/{id}/source` → если `source is None` → 404, иначе 302 на presigned URL (фабрика на `MINIO_PUBLIC_ENDPOINT`).
- В [backend/app/api/health.py](../backend/app/api/health.py) — `GET /health/minio` (HeadBucket).
- Тесты:
  - `tests/storage/test_minio.py` (новая папка): фикстура `minio_client` на живом `home-codespaces-minio-1`, бакет — отдельный per-session (`docbrain-test-{uuid}`), cleanup в teardown. Проверка: `put_object` → `head_object` → `presigned_url`. Маркер `@pytest.mark.integration`, skip если `MINIO_ACCESS_KEY` не задан.
  - `tests/api/test_documents_api.py` — расширить: после `POST /api/documents` → `GET /api/documents/{id}/source` → 302; в БД `source != None`. На время теста — фейковый storage через `dependency_overrides[get_storage]`, чтобы не зависеть от живого MinIO в каждом тесте.
- **Замечание про существующие тесты:** rollback-фикстура откатывает БД, но MinIO не откатывается. В `tests/api/conftest.py` или новом sub-conftest — `dependency_overrides[get_storage] = _stub_storage` (in-memory dict), чтобы только integration-тест ходил в живой MinIO.

**Файлы:** `backend/requirements.txt`, `backend/app/config.py`, `backend/app/storage/__init__.py`, `backend/app/storage/minio.py`, `backend/app/services/documents.py`, `backend/app/api/deps.py`, `backend/app/main.py`, `backend/app/api/documents.py`, `backend/app/api/health.py`, `backend/tests/storage/test_minio.py`, `backend/tests/api/test_documents_api.py` (правки), `backend/tests/api/conftest.py` (или общий), `.env.example` (раскомментировать MinIO-блок + добавить `MINIO_PUBLIC_ENDPOINT`, `MINIO_PRESIGN_TTL_SEC`).

**Коммит:** `feat(backend): интеграция с MinIO для оригиналов документов`.

### Шаг 3.5 — Парсеры PDF, DOCX, URL

- Зависимости: `pypdf`, `python-docx`, `trafilatura` (или `selectolax` + ручной extract — `trafilatura` быстрее ставится и даёт чистый текст из HTML).
- Новые файлы:
  - `backend/app/parsers/pdf.py` — `parse_pdf(payload: bytes) -> str` через `pypdf.PdfReader(io.BytesIO(payload))`, склеить страницы `\n\n`.
  - `backend/app/parsers/docx.py` — `parse_docx(payload: bytes) -> str` через `docx.Document(io.BytesIO(payload))`, склеить параграфы.
  - `backend/app/parsers/url.py` — `async def parse_url(url: str, http: httpx.AsyncClient, max_bytes: int) -> tuple[str, str, str]` (возвращает `(text, filename, content_type)`). GET → если `Content-Length > max_bytes` или поток превышает — `ValueError`. По `Content-Type`: html → `trafilatura.extract(html)`, pdf → `parse_pdf`, docx → `parse_docx`, plain → utf-8.
- В [backend/app/parsers/base.py](../backend/app/parsers/base.py) — добавить расширения `.pdf`, `.docx` в диспатч.
- Новый эндпоинт `POST /api/documents/url` в [backend/app/api/documents.py](../backend/app/api/documents.py):
  - Body `{"url": "https://..."}` (валидация — `HttpUrl` из pydantic).
  - `parse_url(...)` → дальше тот же `create_document(...)` (текст + storage по тому же ключу). `source = "url:{original_url}"` (не S3, потому что оригинал — внешний; либо качаем и тоже льём в MinIO под ключом `url/{document_id}/<filename>` — **выбираем второй вариант для воспроизводимости**).
- Тесты:
  - `tests/test_parsers.py` — добавить unit-тесты PDF/DOCX на фикстурные мини-файлы (положить в `tests/fixtures/sample.pdf`, `tests/fixtures/sample.docx`, генерим скриптом или хардкодим base64).
  - `tests/test_url_parser.py` — `httpx.MockTransport`: HTML → текст без тегов; PDF → текст; превышение `MAX_UPLOAD_BYTES` → `ValueError`.
  - `tests/api/test_documents_url_api.py` — POST `/api/documents/url` с MockTransport на httpx → 201 + чанки в БД.

**Файлы:** `backend/requirements.txt`, `backend/app/parsers/pdf.py`, `backend/app/parsers/docx.py`, `backend/app/parsers/url.py`, `backend/app/parsers/base.py`, `backend/app/api/documents.py`, `backend/tests/fixtures/sample.pdf`, `backend/tests/fixtures/sample.docx`, `backend/tests/test_parsers.py`, `backend/tests/test_url_parser.py`, `backend/tests/api/test_documents_url_api.py`.

**Коммит:** `feat(backend): парсеры PDF/DOCX/URL и эндпоинт /api/documents/url`.

### Шаг 3.6 — Wrap up

- Обновить [decisions.md](decisions.md) блоком `2026-05-?? — Спринт 3 закрыт` с фактическими решениями: `structlog`, request_id middleware, JSON-логи в prod; маппинг ValueError/UnicodeDecodeError → 400; OpenRouter с retry; MinIO под бакет `docbrain-files`; S3-URI как формат `Document.source`; `parse_url` льёт оригинал в MinIO для воспроизводимости.
- Свернуть в [../CLAUDE.md](../CLAUDE.md) «Что сейчас работает» аналогично спринту 2.
- Закрыть `[x]` чек-боксы в этом файле.
- Коммит: `docs: обновить статус по итогам спринта 3`.

## Definition of Done

- Все шаги 3.1–3.6 закрыты `[x]`.
- `EMBEDDING_PROVIDER=openrouter` поднимает приложение и реально эмбеддит smoke-документ (ручная проверка с настоящим ключом).
- `POST /api/documents` (multipart) → файл лежит в MinIO (`mc ls local/docbrain-files`); `Document.source` непустой; `GET /api/documents/{id}/source` отдаёт 302 на работающий presigned URL.
- `POST /api/documents/url` индексирует HTML/PDF/DOCX по URL.
- PDF/DOCX/URL парсеры покрыты тестами на фикстурах.
- Логи приложения в `LOG_FORMAT=json` идут в JSON с `request_id`.
- `ruff check . && ruff format --check . && pytest -v` — зелёные внутри `docbrain-backend`. Integration-тесты MinIO либо запускаются с `MINIO_ACCESS_KEY`, либо корректно скипаются.

## Не делаем в этом спринте

- n8n / Google Drive импорт — спринт 4 (нужны Google OAuth, отдельный контейнер, workflow).
- Next.js фронт, веб-чат — отдельный спринт.
- Telegram-бот / webhook — отдельный спринт.
- Agent с function calling (chat) — отдельный спринт (нужны tool-calling и сохранение истории).
- Authelia + JWT для веб-чата — после фронта.
- CI/CD (GitHub Actions, GHCR, webhook deploy) — отдельный спринт. Шаблоны есть в [../README.md](../README.md).
- Очереди (Celery/ARQ/BackgroundTasks) — после фронта/n8n, когда станет ясно, какие фоновые задачи реально нужны.
- Пагинация/фильтрация по name/type в `/api/documents` — backlog, не критично.
- Reranker, аналитика, история сессий — backlog.

## Открытые вопросы (уточнить по ходу)

1. Endpoint MinIO внутри сети — точно `http://home-codespaces-minio-1:9000`? Проверить через `docker exec docbrain-backend curl -I http://home-codespaces-minio-1:9000/minio/health/live` на старте Шага 3.4.
2. Хранить ли оригинал URL в MinIO или только текст + ссылку? **Решено:** льём в MinIO под ключом `url/{document_id}/{slug}` для воспроизводимости.
3. Лимит по размеру ответа URL — тот же `MAX_UPLOAD_BYTES`? Похоже да, единый.
4. Нужен ли `POST /api/documents/{id}/reembed` (пере-эмбеддинг при смене провайдера)? **Решено:** не в этом спринте.
