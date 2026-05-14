# Спринт 2: модели БД и сырой RAG без LLM

## Цель

Заложить полный data-flow «документ → чанки → векторы → поиск» с заглушкой эмбеддингов. К концу спринта `POST /api/documents` принимает текст, режет на чанки, складывает в БД с фейковыми векторами; `POST /api/search` возвращает top-k чанков по cosine-similarity. Когда позже подключим OpenRouter — заменится только реализация `EmbeddingService`, остальной пайплайн не меняется.

**Почему без LLM сейчас:** нет `OPENROUTER_API_KEY` в `.env`, а откладывать data-layer ради ключа — терять время. Архитектура должна быть готова к замене заглушки одним коммитом.

## Статус спринта

- [x] **Шаг 2.1** — модели `Document`/`Chunk`, миграция `0002_documents_and_chunks` с HNSW-индексом. Закрыт 2026-05-13.
- [x] **Шаг 2.2** — chunker (`app/rag/chunker.py:split_text`, 14 unit-тестов). Закрыт 2026-05-13. Сверх плана: валидации `ValueError` на `size<=0`, `overlap<0`, `overlap>=size`; реэкспорт `split_text` из `app.rag.__init__`.
- [x] **Шаг 2.3** — embedding service (`app/rag/embeddings.py`): `EmbeddingService` Protocol, `StubEmbeddingService` (shake_256 → нормализованный вектор размерности `settings.embedding_dim`), `OpenRouterEmbeddingService` с `NotImplementedError`, фабрика `get_embedding_service()` по `settings.embedding_provider`. 12 unit-тестов. Закрыт 2026-05-14.
- [x] **Шаг 2.4** — парсеры TXT/MD (`app/parsers/`): `parse(filename, payload) -> str` с диспатчем по расширению (`.txt`/`.md`/`.markdown`), `parse_text` (utf-8 + `errors=replace`), `parse_markdown` со срезом YAML-frontmatter, `UnsupportedFormatError(ValueError)` для неизвестных расширений. 18 unit-тестов. Закрыт 2026-05-14.
- [x] **Шаг 2.5** — сервисный слой `app/services/documents.py` (`create_document` склеивает `parse → split → embed → INSERT` в одной транзакции, плюс `list/get/delete_document` с каскадным удалением); Pydantic v2 схемы `app/schemas/document.py` (`DocumentCreate`, `DocumentRead`, `ChunkRead` без поля embedding). 10 integration-тестов через rollback-фикстуру на живом `docbrain-db` (внешняя транзакция + `join_transaction_mode="create_savepoint"`, отдельный engine с `NullPool` под pytest-asyncio). Закрыт 2026-05-14.
- [x] **Шаг 2.6** — API `/api/documents`: POST (multipart, 201 → `DocumentCreatedRead` с `chunks_count`), GET list (`limit`/`offset`), GET by id, DELETE (204). Лимит 10 МБ из `settings.max_upload_bytes` → 413, `UnsupportedFormatError` → 415. `create_document` теперь возвращает `(Document, int)`. Зависимости вынесены в `app/api/deps.py` (`SessionDep`, `EmbedderDep`). Фикстура `db_session` переехала из `tests/services/conftest.py` в `tests/conftest.py`, чтобы её видели и `tests/api/`, и `tests/services/`. 11 API-тестов через `httpx.AsyncClient + ASGITransport` (TestClient несовместим с async-фикстурой rollback'а — другой event loop). Добавлен `python-multipart==0.0.20` в `requirements.txt`. Закрыт 2026-05-14.
- [x] **Шаг 2.7** — retriever + `/api/search`. Закрыт 2026-05-14. `app/rag/retriever.py:search` через `Chunk.embedding.cosine_distance(q)` (оператор `<=>`, HNSW). Сервис `app/services/search.py:search_documents` (embed query → retriever). Роутер `app/api/search.py`: `POST /api/search` body `{query, top_k}` → `list[SearchHit]`. Pydantic-схемы `app/schemas/search.py`: `SearchRequest` (`min_length=1`, `top_k ∈ [1,50]`), `SearchHit` (`document_id/chunk_id/ord/text/distance`). 9 новых тестов (3 service + 6 API). На stub-эмбеддингах query=text чанка даёт distance≈0 — детерминированно.
- [x] **Шаг 2.8** — wrap up. Закрыт 2026-05-14.

## Решения, принятые в начале спринта (2026-05-13)

- **Stub-first**, real OpenRouter — спринт 3. `EmbeddingService` — Protocol, `StubEmbeddingService` (sha256→нормализованный вектор), `OpenRouterEmbeddingService` — заготовка с `NotImplementedError`.
- **Только текст в БД.** Оригинал файла (bytes) не складываем — пойдёт в MinIO в спринте 3. В `Chunk.text` — распарсенный текст.
- **Hard delete.** DELETE документа физически удаляет `Document` и каскадно — `Chunk`-и (FK `ON DELETE CASCADE`).
- **Лимит файла — 10 МБ**, валидация в API. Параметр `MAX_UPLOAD_BYTES` в `.env.example`, поле `settings.max_upload_bytes`.

## Источники истины

- [decisions.md](decisions.md) — принятые решения.
- [dev.md](dev.md) — команды разработки.
- [../INFRA.md](../INFRA.md), [../README.md](../README.md) — VPS и продуктовый план.
- pgvector docs (HNSW, операторы `<=>`, `<#>`, `<->`).

## Архитектурные решения этого спринта (зафиксировать в decisions.md по ходу)

- **Размерность вектора:** `EMBEDDING_DIM=1536` (под `openai/text-embedding-3-small` через OpenRouter). В env-конфиге, не хардкодим.
- **Метрика:** cosine (`vector_cosine_ops`, оператор `<=>`). HNSW-индекс на `chunks.embedding`.
- **Чанкование:** наивное по символам с overlap'ом (`CHUNK_SIZE=800`, `CHUNK_OVERLAP=100`). Без NLP-сегментации, оставим на потом.
- **Парсеры:** TXT и MD на этом спринте. PDF/DOCX/URL — следующий спринт.
- **EmbeddingService:** интерфейс (Protocol) + две реализации:
  - `StubEmbeddingService` — детерминированный хэш текста → нормализованный вектор (для тестов и текущей разработки без LLM).
  - `OpenRouterEmbeddingService` — заготовка с `NotImplementedError`, появится в спринте 3.
  Выбор реализации — по `EMBEDDING_PROVIDER` (`stub` | `openrouter`), дефолт `stub`.
- **Тесты:** integration через живой `docbrain-db`, отдельная тестовая схема + транзакция с rollback на фикстуре. Юниты — на чистую логику чанкования и стаб-эмбеддинг.

## Структура каталогов после спринта

```
backend/app/
├── api/
│   ├── __init__.py
│   ├── documents.py        # POST/GET/DELETE /api/documents
│   └── search.py           # POST /api/search
├── db/
│   ├── session.py          # уже есть
│   └── base.py             # DeclarativeBase
├── models/
│   ├── __init__.py
│   ├── document.py         # Document, Chunk
├── rag/
│   ├── __init__.py
│   ├── chunker.py          # split_text(text, size, overlap) -> list[str]
│   ├── embeddings.py       # EmbeddingService Protocol + StubEmbeddingService
│   └── retriever.py        # search(query, top_k) -> list[Chunk + distance]
├── parsers/
│   ├── __init__.py
│   ├── base.py             # parse(filename, bytes) -> str (router по расширению)
│   ├── text.py             # TXT
│   └── markdown.py         # MD
├── config.py               # расширить: embedding_dim, embedding_provider, chunk_size, chunk_overlap
└── main.py                 # подключить routers
```

## Шаги

### Шаг 2.1 — Модели + миграция

- `app/db/base.py`: `class Base(DeclarativeBase): pass`.
- `app/models/document.py`:
  - `Document(id: UUID pk, name: str, content_type: str, source: str | None, created_at: datetime)`.
  - `Chunk(id: UUID pk, document_id: FK→Document, ord: int, text: str, embedding: Vector(EMBEDDING_DIM), created_at: datetime)`.
  - cascade delete от Document к Chunk.
- Использовать тип `pgvector.sqlalchemy.Vector` (зависимость `pgvector`).
- Миграция `0002_documents_and_chunks`: `CREATE TABLE documents`, `CREATE TABLE chunks` с `embedding vector(1536)`, FK, `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`.
- В `alembic/env.py` подключить `target_metadata = Base.metadata` (или оставить ручной режим — миграцию пишем руками всё равно).
- Проверка: `alembic upgrade head` → `\d+ chunks` показывает индекс HNSW.
- Коммит: `feat(backend): модели Document/Chunk и миграция с HNSW-индексом`.

### Шаг 2.2 — Чанкование

- `app/rag/chunker.py`: `def split_text(text: str, size: int = 800, overlap: int = 100) -> list[str]`. Делим по символам, сохраняем overlap. Edge-cases: пустая строка → `[]`, `len(text) <= size` → `[text]`.
- Тесты: пустой ввод, короткий текст, длинный с проверкой overlap, граничные размеры.
- Коммит: `feat(backend): наивный chunker с overlap + тесты`.

### Шаг 2.3 — Embedding service (stub)

- `app/rag/embeddings.py`:
  - `class EmbeddingService(Protocol): async def embed(self, texts: list[str]) -> list[list[float]]`.
  - `class StubEmbeddingService`: хэш текста (`hashlib.sha256` → bytes → нормализованный float[]). Детерминированно. Размерность = `settings.embedding_dim`.
  - `get_embedding_service() -> EmbeddingService` — фабрика по `settings.embedding_provider`.
- В `config.py`: `embedding_provider: Literal["stub", "openrouter"] = "stub"`, `embedding_dim: int = 1536`, `chunk_size: int = 800`, `chunk_overlap: int = 100`.
- Тесты: детерминированность, длина вектора, нормализация (||v||=1).
- Коммит: `feat(backend): EmbeddingService Protocol + детерминированный stub`.

> **Альтернатива: real-first.** `OPENROUTER_API_KEY` уже в `.env` (см. [decisions.md](decisions.md)) — можно сразу делать `OpenRouterEmbeddingService` через `httpx.AsyncClient` к `https://openrouter.ai/api/v1/embeddings`, держать `StubEmbeddingService` только как fallback для unit-тестов (через `dependency_overrides`). Решение — в начале спринта, до Шага 2.1.

### Шаг 2.4 — Парсеры

- `app/parsers/base.py`: `def parse(filename: str, payload: bytes) -> str` — диспатч по расширению.
- TXT: `payload.decode("utf-8", errors="replace")`.
- MD: то же + опционально удалить frontmatter `---...---`.
- Неизвестное расширение → `UnsupportedFormatError`.
- Тесты на каждый парсер + ошибка для `.bin`.
- Коммит: `feat(backend): парсеры TXT/MD`.

### Шаг 2.5 — Repository / use-cases

- `app/services/documents.py` (или прямо в роутере, если просто):
  - `async def create_document(session, name, content_type, payload, embedder, chunker_cfg) -> Document` — парсит, чанкует, эмбеддит, INSERT'ит документ + чанки в одной транзакции.
  - `async def list_documents(session)`, `async def get_document(session, id)`, `async def delete_document(session, id)`.
- Никакой Pydantic-бизнес-логики в сервисах — сервисы работают с ORM, роутеры маппят в Pydantic-схемы.
- Pydantic-схемы — в `app/schemas/document.py` (`DocumentRead`, `DocumentCreate`, `ChunkRead`).
- Коммит: `feat(backend): сервисный слой documents`.

### Шаг 2.6 — API documents

- `app/api/documents.py`:
  - `POST /api/documents` (multipart: file) — 201, возвращает `DocumentRead` + кол-во чанков.
  - `GET /api/documents` — пагинация (`limit`, `offset`).
  - `GET /api/documents/{id}` — 200 / 404.
  - `DELETE /api/documents/{id}` — 204 / 404, каскадно удаляет чанки.
- `main.py`: `app.include_router(documents_router, prefix="/api")`.
- Integration-тесты: загрузить TXT → проверить, что чанки в БД; GET список; GET по id; DELETE → 404.
- Коммит: `feat(backend): /api/documents CRUD`.

### Шаг 2.7 — Retriever + /api/search

- `app/rag/retriever.py`: `async def search(session, query_embedding, top_k) -> list[tuple[Chunk, float]]` — SQL `ORDER BY embedding <=> :q LIMIT :k`, возвращает чанки + расстояние.
- `app/api/search.py`: `POST /api/search` body `{query: str, top_k: int = 5}` → эмбеддит query через `get_embedding_service()` → вызывает retriever → возвращает чанки с document_id, ord, text, distance.
- Integration-тест: загрузить 2 документа, выполнить search, проверить, что top-1 совпадает по содержанию (на стаб-эмбеддингах — детерминированно).
- Коммит: `feat(backend): retriever и /api/search`.

### Шаг 2.8 — Wrap up

- Обновить [decisions.md](decisions.md) с фактическими решениями спринта (если что-то изменилось по ходу).
- Обновить [../CLAUDE.md](../CLAUDE.md) только в разделе «Что сейчас работает» (1–2 строки).
- Коммит: `docs: обновить статус по итогам спринта 2`.

## Definition of Done

- Все эндпоинты `/api/documents/*` и `/api/search` отвечают, покрыты тестами.
- Миграция `0002` применяется чисто на пустой БД и на БД с применённой `0001`.
- `ruff check . && ruff format --check . && pytest -v` — зелёные.
- В `chunks` лежат векторы размерности `EMBEDDING_DIM`, индекс HNSW виден в `\d+ chunks`.
- `POST /api/search` возвращает осмысленный top-k на стаб-эмбеддингах (детерминированно).

## Не делаем в этом спринте

- OpenRouter — отдельный спринт, нужен ключ.
- Tool-calling agent — спринт 4.
- Frontend, n8n, Telegram, CI/CD — позже.
- Парсеры PDF/DOCX/URL — спринт 3.
- MinIO для исходников — спринт 3 (сейчас храним только текст в БД).
- Аутентификация JWT — спринт после фронта.

## Открытые вопросы (решить в новой сессии)

1. Хранить ли оригинал файла (`payload`) в БД (BLOB) или только текст? Голос за «только текст сейчас, оригинал в MinIO позже».
2. Soft delete документов или hard? Голос за hard на этом этапе.
3. Где лимиты на размер файла? Предложение: 10 МБ на старте, валидация в API.
