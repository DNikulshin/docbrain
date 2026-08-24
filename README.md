# DocBrain

**AI-консультант по корпоративной документации**  
RAG · Agent with function calling · n8n · Telegram · Next.js

[![CI](https://github.com/DNikulshin/docbrain/actions/workflows/ci.yml/badge.svg)](https://github.com/DNikulshin/docbrain/actions/workflows/ci.yml)
[![CD](https://github.com/DNikulshin/docbrain/actions/workflows/cd.yml/badge.svg)](https://github.com/DNikulshin/docbrain/actions/workflows/cd.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

| | |
|---|---|
| 🌐 **Live Demo** | [backend-latest-2ax3.onrender.com](https://backend-latest-2ax3.onrender.com) |
| 📚 **API Docs** | [Swagger UI](https://backend-latest-2ax3.onrender.com/docs) |
| 🩺 **Health** | [`/health`](https://backend-latest-2ax3.onrender.com/health) |

---

## О проекте

**DocBrain** — production-ready система, которая автоматически отвечает на вопросы по корпоративной документации.

Система объединяет:

- **RAG** на PostgreSQL + pgvector
- **LLM-агент** с function calling (поиск по документам, источники)
- **Синхронизацию** документов из Google Drive через n8n
- **Веб-чат** на Next.js 15
- **Telegram-бота**
- **Админ-панель**

Проект закрывает пробел в портфолио fullstack / AI-интегратора и готов к демонстрации заказчикам.

---

## Возможности

| Возможность | Описание |
|-------------|----------|
| 🔍 **Семантический поиск** | Эмбеддинги через OpenRouter + pgvector |
| 🤖 **Agent + tools** | Function calling: поиск документов, получение источников |
| 📄 **Парсеры** | PDF, DOCX, Markdown, TXT, URL |
| 🔄 **Автосинхронизация** | n8n → Google Drive (pull каждые 6 часов) |
| 💬 **Веб-чат** | Next.js 15, JWT-авторизация |
| 📱 **Telegram** | Webhook, идентификация по `chat_id` |
| 🗄️ **Хранилище** | MinIO (S3) для исходных файлов |
| 🔒 **Безопасность** | JWT, Authelia (для n8n), изоляция БД |

---

## Архитектура

```mermaid
graph TB
    subgraph VPS ["VPS · nikulshin-dev.online"]
        Caddy["Caddy<br/>reverse proxy + HTTPS"]
        Authelia["Authelia<br/>SSO / 2FA"]

        subgraph Stack ["DocBrain Compose"]
            Backend["FastAPI<br/>RAG + Agent"]
            Web["Next.js 15<br/>чат / админка"]
            N8N["n8n<br/>workflows"]
            DB[("PostgreSQL<br/>+ pgvector")]
            MinIO["MinIO<br/>S3 storage"]
        end
    end

    TG["Telegram Bot"] -->|webhook| Backend
    User["Пользователь"] -->|HTTPS| Caddy
    Caddy -->|/api/*| Backend
    Caddy -->|/*| Web
    Caddy -->|/n8n/*| Authelia
    Authelia -->|auth ok| N8N
    N8N -->|pull every 6h| GDrive["Google Drive"]
    N8N -->|POST /api/import| Backend
    Backend -->|embeddings| DB
    Backend -->|raw files| MinIO
    Web -->|upload| MinIO
    Web -->|REST| Backend

    style Caddy fill:#4CAF50,stroke:#2E7D32,color:#fff
    style Authelia fill:#FF9800,stroke:#E65100,color:#fff
    style Backend fill:#2196F3,stroke:#1565C0,color:#fff
    style Web fill:#9C27B0,stroke:#6A1B9A,color:#fff
    style DB fill:#607D8B,stroke:#37474F,color:#fff
    style MinIO fill:#00BCD4,stroke:#00838F,color:#fff
```

### Ключевые решения

- **PostgreSQL + pgvector** — отдельный контейнер `docbrain-db` (изоляция)
- **Веб-чат** — публичный, JWT на уровне FastAPI; Telegram — по `chat_id`
- **OpenRouter** — единый ключ для эмбеддингов и чата
- **n8n** — за Authelia, импорт из Google Drive (cron pull)
- **MinIO** — бакет `docbrain-files` для исходников

Подробности инфраструктуры — в [`INFRA.md`](INFRA.md).

---

## Стек технологий

| Слой | Технологии |
|------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Alembic, pgvector |
| LLM / RAG | OpenRouter, text-embedding-3-small, Claude 3.5 Sonnet |
| Frontend | Next.js 15, React, TypeScript |
| Automation | n8n |
| Storage | PostgreSQL 16 + pgvector, MinIO |
| Infra | Docker, Caddy, Authelia, GitHub Actions |
| Bot | Telegram Bot API (webhook) |

---

## Структура репозитория

```text
docbrain/
├── .github/workflows/
│   ├── ci.yml              # тесты, линтинг, сборка
│   └── cd.yml              # push образа в GHCR
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/         # document, session
│   │   ├── rag/            # embedding, vector_store, retriever
│   │   ├── agents/         # function_agent (tool calling)
│   │   ├── tools/          # search_docs, get_sources
│   │   ├── api/            # chat, documents, import, telegram
│   │   ├── db/
│   │   └── utils/          # parsers, minio_client
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/                # page.tsx, admin/, layout.tsx
│   ├── components/
│   ├── lib/api.ts
│   └── Dockerfile
├── n8n/workflows/
│   └── google_drive_sync.json
├── docs/
├── docker-compose.yml
├── .env.example
├── Makefile
└── README.md
```

---

## Быстрый старт (локально)

### 1. Клонировать и подготовить окружение

```bash
git clone https://github.com/DNikulshin/docbrain.git
cd docbrain
cp .env.example .env
# Заполните OPENROUTER_API_KEY и другие обязательные переменные
```

### 2. Запустить через Docker Compose

```bash
docker compose up -d --build
```

### 3. Проверить

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "service": "docbrain-backend",
  "version": "0.1.0",
  "environment": "development"
}
```

> **Примечание.** Без настроенных MinIO и n8n будут работать только RAG и API. Для эмбеддингов нужен `OPENROUTER_API_KEY`.

### Альтернатива: образ из GHCR

```bash
# PostgreSQL + pgvector
docker run -d --name docbrain-db \
  -e POSTGRES_USER=docbrain \
  -e POSTGRES_PASSWORD=securepassword \
  -e POSTGRES_DB=docbrain \
  pgvector/pgvector:pg16

# Backend
docker run -d --name docbrain-backend \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://docbrain:securepassword@docbrain-db:5432/docbrain" \
  --link docbrain-db \
  ghcr.io/dnikulshin/docbrain/backend:latest
```

---

## Примеры API

### Загрузка документа (файл)

```bash
curl -X POST http://localhost:8000/api/documents \
  -F "file=@example.txt"
```

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "example.txt",
  "content_type": "text/plain",
  "source": "s3://docbrain-files/.../example.txt",
  "created_at": "2026-05-18T12:00:00Z",
  "chunks_count": 1
}
```

### Загрузка по URL

```bash
curl -X POST http://localhost:8000/api/documents/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/document.pdf"}'
```

### Поиск

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "политика отпусков", "top_k": 3}'
```

```json
[
  {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
    "ord": 0,
    "text": "Политика отпусков: 28 календарных дней...",
    "distance": 0.123
  }
]
```

Полная документация — [Swagger UI](https://backend-latest-2ax3.onrender.com/docs).

![Пример загрузки в Swagger](docs/swagger-upload.png)

---

## Тесты

### Backend (pytest)

```bash
cd backend
pip install -r requirements.txt
pytest tests --cov=app
```

Пример:

```python
@pytest.mark.asyncio
async def test_search_similar():
    embedding = await get_embedding("политика отпусков")
    results = await search_similar(embedding, limit=3)
    assert len(results) <= 3
```

### Frontend (Jest)

```bash
cd frontend
npm ci && npm test
```

CI запускает оба пайплайна на каждый push / PR (см. `.github/workflows/ci.yml`).

---

## Развёртывание на VPS

Подробная пошаговая инструкция (Caddy, Authelia, MinIO, n8n, webhook Telegram) описана в разделе ниже и в [`INFRA.md`](INFRA.md).

### Кратко

1. Создать бакет `docbrain-files` в MinIO  
2. Заполнить `.env` (OpenRouter, Postgres, Telegram, MinIO, JWT, n8n, Google Drive)  
3. Поднять стек: `docker compose up -d --build`  
4. Добавить маршруты в Caddyfile  
5. Импортировать workflow Google Drive в n8n  
6. Установить Telegram webhook:

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://docbrain.nikulshin-dev.online/tg/webhook"
```

### Пример Caddy (фрагмент)

```caddy
docbrain.nikulshin-dev.online {
  handle /tg/webhook* {
    reverse_proxy docbrain-backend:8000
  }
  handle /api/* {
    reverse_proxy docbrain-backend:8000
  }
  handle {
    reverse_proxy docbrain-web:3000
  }
}

n8n.nikulshin-dev.online {
  import authelia
  reverse_proxy docbrain-n8n:5678
}
```

---

## CI/CD

| Workflow | Триггер | Действие |
|----------|---------|----------|
| **CI** | push / PR | pytest + coverage, frontend tests |
| **CD** | push в `main` (backend/**) | сборка и push образа в `ghcr.io/dnikulshin/docbrain/backend` |

Образы доступны без VPS — можно запускать где угодно.

```bash
docker pull ghcr.io/dnikulshin/docbrain/backend:latest
```

---

## Мониторинг

```bash
docker logs docbrain-backend -f
docker logs docbrain-n8n -f
```

Caddy access log и метрики MinIO — через существующую инфраструктуру VPS.

---

## Roadmap

- [ ] История сессий чата (сохранение в БД)
- [ ] Загрузка документов прямо из веб-чата
- [ ] Фоновая обработка больших PDF (Celery + Redis)
- [ ] Reranker (Cohere / cross-encoder)
- [ ] Интеграционные тесты с реальным LLM в CI
- [ ] Дашборд аналитики (запросы, тональность, популярные темы)

---

## Лицензия

[MIT](LICENSE) — можно свободно использовать в портфолио и коммерческих проектах.

---

## Контакты

**Дмитрий Никульшин**

- Telegram: [@nikulshin_dev](https://t.me/nikulshin_dev)
- GitHub: [DNikulshin](https://github.com/DNikulshin)
- Портфолио: [dnikulshin.ru](https://dnikulshin.ru)
