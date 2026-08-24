# DocBrain — AI-консультант по документации с RAG, n8n и Telegram

[![CI](https://github.com/DNikulshin/docbrain/actions/workflows/ci.yml/badge.svg)](https://github.com/DNikulshin/docbrain/actions/workflows/ci.yml)
[![CD](https://github.com/DNikulshin/docbrain/actions/workflows/cd.yml/badge.svg)](https://github.com/DNikulshin/docbrain/actions/workflows/cd.yml)

> **DocBrain** — production-ready система для автоматического ответа на вопросы по корпоративной документации.  
> Сочетает RAG (pgvector), agent с function calling, синхронизацию документов через n8n (Google Drive), веб-чат на Next.js, Telegram бота и админку.  
> Проект закрывает пробел в портфолио fullstack/AI-интегратора и может быть показан заказчикам.

---

## 📐 Архитектура

```mermaid
graph TB
    subgraph VPS [VPS nikulshin-dev.online]
        Caddy[Caddy<br/>reverse proxy + HTTPS]
        Authelia[Authelia<br/>SSO/2FA]

        subgraph DocBrain [DocBrain Compose Stack]
            Backend[FastAPI<br/>RAG + Agent]
            Web[Next.js 15<br/>веб-чат / админка]
            N8N[n8n<br/>workflow automation]
            DB[(PostgreSQL<br/>+ pgvector)]
            MinIO[MinIO<br/>S3-совместимое хранилище]
        end

        Existing[Другие сервисы<br/>scan-agent, portainer, ...]
    end

    TG[Telegram Bot] -->|webhook| Backend
    User[Пользователь] -->|HTTPS| Caddy
    Caddy -->|/api/*| Backend
    Caddy -->|/*| Web
    Caddy -->|/n8n/*| Authelia
    Authelia -->|if auth ok| N8N
    N8N -->|pull every 6h| GDrive[Google Drive API]
    N8N -->|POST /api/import| Backend
    Backend -->|эмбеддинги| DB
    Backend -->|сырые файлы| MinIO
    Web -->|загрузка файлов| MinIO
    Web -->|REST API| Backend

    style Caddy fill:#4CAF50,stroke:#2E7D32
    style Authelia fill:#FF9800
    style Backend fill:#2196F3
    style Web fill:#9C27B0
    style DB fill:#607D8B
```

Ключевые решения (согласно INFRA.md):

- **PostgreSQL + pgvector** – отдельный контейнер `docbrain-db` (изоляция от scan-agent).
- **Веб-чат** – публичный, но с JWT-авторизацией на уровне FastAPI (Telegram-бот идентифицирует по `chat_id`).
- **OpenRouter** – единый API-ключ для всех LLM (эмбеддинги + чат).
- **n8n** – за Authelia, импорт документов из Google Drive (pull-mode по cron).
- **MinIO** – используется существующий инстанс для хранения исходников файлов (бакет `docbrain-files`).

## 🗂 Структура репозитория

```text
docbrain/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # тесты, линтинг, сборка
│       └── cd.yml                  # деплой на VPS через webhook
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/
│   │   │   ├── document.py
│   │   │   └── session.py
│   │   ├── rag/
│   │   │   ├── embedding.py        # OpenRouter эмбеддинги
│   │   │   ├── vector_store.py     # pgvector
│   │   │   └── retriever.py
│   │   ├── agents/
│   │   │   └── function_agent.py   # tool calling
│   │   ├── tools/
│   │   │   ├── search_docs.py
│   │   │   └── get_sources.py
│   │   ├── api/
│   │   │   ├── chat.py
│   │   │   ├── documents.py
│   │   │   ├── import.py
│   │   │   └── telegram.py
│   │   ├── db/
│   │   │   └── session.py
│   │   └── utils/
│   │       ├── parsers.py          # PDF, DOCX, MD, URL
│   │       └── minio_client.py
│   ├── tests/
│   │   ├── test_rag.py
│   │   ├── test_agent.py
│   │   └── test_api.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic/                    # миграции
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # веб-чат
│   │   ├── admin/
│   │   │   └── page.tsx            # админка
│   │   └── layout.tsx
│   ├── components/
│   ├── lib/
│   │   └── api.ts
│   ├── Dockerfile
│   └── next.config.js
├── n8n/
│   ├── workflows/
│   │   └── google_drive_sync.json
│   └── Dockerfile                  # опционально
├── docker-compose.yml
├── .env.example
├── Makefile
└── README.md
```

## 🔌 Примеры использования API

### Загрузка документа (TXT)

```bash
curl -X POST http://localhost:8000/api/documents \
  -F "file=@example.txt"
```

Ответ:

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

### Поиск по запросу

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "политика отпусков", "top_k": 3}'
```

Ответ:

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

### Загрузка документа по URL

```bash
curl -X POST http://localhost:8000/api/documents/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/document.pdf"}'
```

Ответ аналогичен загрузке файла.

## 🧪 Тесты

### Backend (pytest)

```python
# backend/tests/test_rag.py
import pytest
from app.rag.vector_store import search_similar
from app.rag.embedding import get_embedding

@pytest.mark.asyncio
async def test_search_similar():
    embedding = await get_embedding("политика отпусков")
    results = await search_similar(embedding, limit=3)
    assert len(results) <= 3
    assert all("similarity" in r for r in results)

# backend/tests/test_agent.py
@pytest.mark.asyncio
async def test_agent_search_tool():
    from app.agents.function_agent import run_agent
    answer, sources = await run_agent("Сколько дней отпуска?")
    assert len(answer) > 0
    assert isinstance(sources, list)
```

### Frontend (Jest + React Testing Library)

```ts
// frontend/__tests__/Chat.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import Chat from '../components/Chat';

test('отправляет сообщение и получает ответ', async () => {
  render(<Chat />);
  fireEvent.change(screen.getByPlaceholderText(/спросите/i), { target: { value: 'отпуск' } });
  fireEvent.click(screen.getByText('Отправить'));
  expect(await screen.findByText(/ответ/i)).toBeInTheDocument();
});
```

### Запуск тестов в CI

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests --cov=app

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: cd frontend && npm ci && npm test
```

## 🔌 Примеры использования API

### Загрузка документа (TXT)

```bash
curl -X POST http://localhost:8000/api/documents \
  -F "file=@example.txt"
```

Ответ:

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

### Поиск по запросу

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "политика отпусков", "top_k": 3}'
```

Ответ:

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

### Загрузка документа по URL

```bash
curl -X POST http://localhost:8000/api/documents/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/document.pdf"}'
```

Ответ аналогичен загрузке файла.

## 🚀 Разворачивание на VPS (пошагово)

> **Этот раздел опционален** и предназначен для продакшн-развёртывания на подготовленной инфраструктуре (VPS с Caddy, Authelia, MinIO). Если у вас нет такой инфраструктуры, вы можете использовать инструкции из раздела «🐳 Развёртывание образа (без VPS)».

### Предварительные требования (уже выполнены согласно INFRA.md)

- VPS с Docker, Caddy, Authelia, MinIO, сетью `home-codespaces_proxy`.
- Домены `*.nikulshin-dev.online` указывают на VPS.
- Доступ к code-server через `code.nikulshin-dev.online`.

### Шаг 1. Создание бакета в MinIO

```bash
# через UI minio.nikulshin-dev.ru или CLI
docker exec home-codespaces-minio-1 mc mb local/docbrain-files
docker exec home-codespaces-minio-1 mc policy set download local/docbrain-files
```

### Шаг 2. Настройка переменных окружения

Создайте `/opt/home-codespaces/projects/docbrain/.env` на основе `.env.example`:

```ini
# OpenRouter
OPENROUTER_API_KEY=sk-or-v1-...
EMBEDDING_MODEL=openai/text-embedding-3-small
CHAT_MODEL=anthropic/claude-3.5-sonnet

# PostgreSQL (отдельный контейнер)
POSTGRES_USER=docbrain
POSTGRES_PASSWORD=securepassword
POSTGRES_DB=docbrain
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@docbrain-db:5432/${POSTGRES_DB}

# Telegram
TELEGRAM_BOT_TOKEN=789:ABC... (новый бот)

# MinIO
MINIO_ENDPOINT=s3.nikulshin-dev.ru
MINIO_ACCESS_KEY=ваш_ключ
MINIO_SECRET_KEY=ваш_секрет
MINIO_BUCKET=docbrain-files

# JWT для веб-чата
JWT_SECRET_KEY=your-secret-key

# n8n
N8N_ENCRYPTION_KEY=some-random-key
GOOGLE_DRIVE_CLIENT_ID=xxx
GOOGLE_DRIVE_CLIENT_SECRET=xxx
GOOGLE_DRIVE_REFRESH_TOKEN=xxx
```

### Шаг 3. Подготовка docker-compose.yml для DocBrain

Создайте `/home/coder/projects/docbrain/docker-compose.yml`:

```yaml
version: "3.8"

networks:
  proxy:
    external: true
    name: home-codespaces_proxy

services:
  docbrain-db:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata_docbrain:/var/lib/postgresql/data
    networks:
      - proxy

  docbrain-backend:
    build: ./backend
    restart: unless-stopped
    env_file: .env
    environment:
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ./backend:/app # для разработки, в production убрать
    depends_on:
      - docbrain-db
    networks:
      - proxy

  docbrain-web:
    build: ./frontend
    restart: unless-stopped
    environment:
      - NEXT_PUBLIC_API_URL=https://api.docbrain.nikulshin-dev.online
    networks:
      - proxy

  docbrain-n8n:
    image: n8nio/n8n:latest
    restart: unless-stopped
    environment:
      - N8N_HOST=n8n.nikulshin-dev.online
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://n8n.nikulshin-dev.online
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - GENERIC_TIMEZONE=Europe/Moscow
      - N8N_BASIC_AUTH_ACTIVE=false # Authelia
    volumes:
      - n8n_data:/home/node/.n8n
      - ./n8n/workflows:/home/node/workflows
    networks:
      - proxy

volumes:
  pgdata_docbrain:
  n8n_data:
```

### Шаг 4. Обновление Caddyfile

Добавьте в `/opt/home-codespaces/Caddyfile`:

```caddy
# DocBrain
docbrain.nikulshin-dev.online {
    # Публичный webhook для Telegram (без Authelia)
    handle /tg/webhook* {
        reverse_proxy docbrain-backend:8000
    }
    # API для веб-чата и импорта (тоже публичные, но с JWT-проверкой в коде)
    handle /api/* {
        reverse_proxy docbrain-backend:8000
    }
    # Next.js фронт
    handle {
        reverse_proxy docbrain-web:3000
    }
}

# n8n - только через Authelia
n8n.nikulshin-dev.online {
    import authelia
    reverse_proxy docbrain-n8n:5678
}
```

После правок:

```bash
docker exec home-codespaces-caddy-1 caddy reload --config /etc/caddy/Caddyfile
```

### Шаг 5. Запуск DocBrain

```bash
cd /home/coder/projects/docbrain
docker-compose up -d --build
```

### Шаг 6. Настройка n8n workflow (Google Drive → импорт)

1. Зайдите в `https://n8n.nikulshin-dev.online` (пройдите Authelia).
2. Добавьте credentials Google Drive OAuth2.
3. Импортируйте workflow из `n8n/workflows/google_drive_sync.json` (см. пример ниже).
4. Активируйте workflow (каждые 6 часов).

Пример workflow (JSON):

```json
{
  "name": "Google Drive to DocBrain",
  "nodes": [
    {
      "name": "Schedule",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": { "rule": { "interval": [{ "hours": 6 }] } }
    },
    {
      "name": "Google Drive List",
      "type": "n8n-nodes-base.googleDrive",
      "parameters": { "operation": "list", "folderId": "your_folder_id" }
    },
    {
      "name": "HTTP Request",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://docbrain-backend:8000/api/import-from-n8n",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": { "X-API-Key": "={{$env.DOCBRAIN_IMPORT_KEY}}" },
        "body": {
          "file_url": "={{$json.webContentLink}}",
          "name": "={{$json.name}}"
        }
      }
    }
  ]
}
```

### Шаг 7. Настройка Telegram webhook

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -d "url=https://docbrain.nikulshin-dev.online/tg/webhook"
```

## ⚙️ GitHub Actions CI/CD

### Файл `.github/workflows/cd.yml` (сборка образа в GHCR)

```yaml
name: Build and Push Image

on:
  push:
    branches: [main]
    paths:
      - "backend/**"
      - "docker-compose.yml"
      - ".github/workflows/cd.yml"
  workflow_dispatch: # ручной запуск для пересборки

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/backend

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push backend
        uses: docker/build-push-action@v6
        with:
          context: ./backend
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Этот пайплайн **не требует VPS** — он только собирает образ и публикует его в GitHub Container Registry. Вы можете скачать и запустить его где угодно (локально, на любом облаке).  
Если у вас есть VPS, вы можете добавить шаг с webhook-деплоем (пример закомментирован в репозитории).

## 🐳 Развёртывание образа (без VPS)

Образ публикуется в GitHub Container Registry. Вы можете запустить его локально или на любом сервере с Docker.

### Шаг 1. Скачать образ

```bash
docker pull ghcr.io/dnikulshin/docbrain/backend:latest
```

### Шаг 2. Поднять PostgreSQL с pgvector

```bash
docker run -d --name docbrain-db \
  -e POSTGRES_USER=docbrain \
  -e POSTGRES_PASSWORD=securepassword \
  -e POSTGRES_DB=docbrain \
  pgvector/pgvector:pg16
```

### Шаг 3. Запустить backend

```bash
docker run -d --name docbrain-backend \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://docbrain:securepassword@docbrain-db:5432/docbrain" \
  --link docbrain-db \
  ghcr.io/dnikulshin/docbrain/backend:latest
```

### Шаг 4. Проверить работу

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ: `{"status":"ok","service":"docbrain-backend","version":"0.1.0","environment":"development"}`

### Запуск через docker-compose (локально)

В корне репозитория уже есть `docker-compose.yml`. Для локального запуска с образами из GHCR можно использовать:

```bash
docker-compose up -d
```

Переменные окружения задаются в файле `.env` (скопируйте `.env.example` и заполните).

> **Примечание:** При локальном запуске MinIO, n8n и другие интеграции не будут работать, если они не настроены. Для тестирования RAG достаточно PostgreSQL и OpenRouter API-ключа (если вы используете реальные эмбеддинги, установите `EMBEDDING_PROVIDER=openrouter` и укажите `OPENROUTER_API_KEY`).

## 📊 Мониторинг и логи

- Логи backend: `docker logs docbrain-backend -f`
- n8n логи: `docker logs docbrain-n8n`
- Caddy логи: `docker exec home-codespaces-caddy-1 tail -f /var/log/caddy/access.log`
- MinIO метрики: через `minio.nikulshin-dev.ru`

## 🧭 Дальнейшие улучшения (roadmap)

- Поддержка чата с историей сессий (сохранение в БД)
- Возможность загружать документы через веб-чат (уже есть MinIO)
- Асинхронная фоновая обработка больших PDF (Celery + Redis)
- Reranker (Cohere или cross-encoder) для повышения качества поиска
- CI-пайплайн с интеграционными тестами на реальном LLM
- Дашборд аналитики (количество запросов, тональность, популярные темы)

## 📝 Лицензия

MIT (можно свободно использовать в портфолио и коммерческих проектах).

## 🙋 Контакты

- Автор: Дмитрий Никульшин
- Telegram: [@nikulshin_dev](https://t.me/nikulshin_dev)
- GitHub: [DNikulshin](https://github.com/DNikulshin)
- Портфолио: [dnikulshin.ru](https://dnikulshin.ru)
