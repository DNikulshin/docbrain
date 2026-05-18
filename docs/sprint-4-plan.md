# Спринт 4: n8n / Google Drive Sync

Дата закрытия: **2026-05-18**

## Цель

Автоматический импорт документов из Google Drive в DocBrain через n8n (pull каждые 6 ч).

## Ключевые решения

- Повторный прогон с уже импортированным файлом → **перезаписать** (удалить старый + создать новый)
- Отдельный endpoint `/api/import/gdrive` (не расширять `/api/documents`)
- Auth: `X-API-Key` заголовок, только на `/api/import/*`; если `DOCBRAIN_API_KEY` не задан — dev mode без auth

## Шаги

- [x] **4.1** — `X-API-Key` auth: `DOCBRAIN_API_KEY` в `config.py`, `APIKeyDep` в `deps.py`
- [x] **4.2** — `source_id: str | None` (UNIQUE NULL) в модели `Document` + миграция `0003`
- [x] **4.3** — `POST /api/import/gdrive`: `import_gdrive_document` (find → delete → create), роутер `api/import_.py`, схема `GdriveImportRead`
- [x] **4.4** — `docbrain-n8n` в `docker-compose.yml` (image `n8nio/n8n:latest`, volume `n8n_data`, env `N8N_ENCRYPTION_KEY`/`DOCBRAIN_API_KEY`)
- [x] **4.5** — n8n workflow JSON `n8n/gdrive-import.json` (schedule 6h → list → filter MIME → download → POST backend)

## Результат

- **116 тестов, 5 skipped** (MinIO integration без ключа)
- Все коммиты запушены в `main`

## Нюансы

- **`import_.py`** — имя с подчёркиванием, чтобы не конфликтовать с Python builtin `import`
- **`delete_document` → `create_document`** — две отдельные транзакции; atomicity не требуется (n8n повторит при ошибке)
- **`GDRIVE_FOLDER_ID`** задаётся как переменная в n8n UI (Variables), не в коде
- **`generate_presigned_url` — sync** (aiobotocore), актуально при работе с MinIO в import endpoint

## Следующий спринт — 5

Вероятные темы (уточнить в начале сессии):
- Telegram-бот (webhook `/tg/webhook`, chat_id → `/api/search`)
- Веб-чат frontend (Next.js 15, JWT auth)
- CI/CD (GitHub Actions → GHCR → webhook деплой)
