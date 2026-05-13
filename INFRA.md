# VPS-инфра для проекта docbrain

Документ-брифинг для DeepSeek-чата: что уже есть на VPS, чем пользоваться, что доставить под docbrain (RAG-сервис с FastAPI + Next.js + n8n + Postgres/pgvector + Telegram bot).

Дата снимка: **2026-05-13**. Хост: VPS, домены `nikulshin-dev.online` и `nikulshin-dev.ru`. Wildcard DNS `*.nikulshin-dev.online` уже настроен.

---

## 1. Архитектура хоста (что уже крутится)

Всё хозяйство живёт в `/opt/home-codespaces/` и поднято через **один корневой docker compose** (`docker-compose.yml`, проект `home-codespaces`). Все сервисы — в одной docker-сети `home-codespaces_proxy` (она же `proxy`).

### Уже запущенные контейнеры

| Контейнер | Образ | Назначение |
|---|---|---|
| `home-codespaces-caddy-1` | `caddy:latest` | Reverse proxy + автоматический HTTPS (ACME HTTP-01). Слушает `:80` / `:443` на хосте. |
| `authelia` + `redis-auth` | `authelia/authelia:latest`, `redis:7-alpine` | SSO/2FA. Подключается к любому сабдомену через snippet `import authelia`. UI на `auth.nikulshin-dev.online`. |
| `home-codespaces-codeserver-1` | свой build (`Dockerfile.codeserver`) | VS Code Server (где я сейчас работаю). Все проекты — в `/home/coder/projects/` (= `/opt/home-codespaces/projects/` на хосте). Маунтит `docker.sock`. |
| `home-codespaces-webssh-1` | `ghcr.io/dnikulshin/web-ssh-client` | Web-SSH под Authelia. |
| `home-codespaces-portainer-1` | `portainer/portainer-ce:latest` | UI для docker. |
| `home-codespaces-webhook-1` | `alpine` + `webhook` + `docker-cli-compose` | Принимает GitHub-webhook'и, делает `compose pull && up -d`. Точка для CI деплоя. |
| `postgres-provision` | `postgres:16-alpine` | **Центральный PostgreSQL** для всех проектов. Открыт порт `5432` наружу (ufw — только GitHub Actions). |
| `db-provisioner` | свой build (FastAPI) | API создания/удаления БД, хранит метаданные в `managed_databases`. За Caddy `/api/*` на `db.nikulshin-dev.online`, инжектится `X-API-Key`. |
| `db-ui` | `nginx:alpine` | HTML/JS UI к provisioner'у, закрыт Authelia. |
| `dashboard` | `ghcr.io/dnikulshin/scan-agent/dashboard` | Next.js dashboard scan-agent'а. Шаблон деплоя 1-в-1 годится для docbrain. |
| `home-codespaces-minio-1` | `minio/minio:latest` | S3-совместимое хранилище. Бакет `db-backups` уже используется под бэкапы postgres. |
| `portfolio-next-*` | свой стек | Чужой проект (личное портфолио), не трогать. |
| `3xui-3xui-1` | `ghcr.io/mhsanaei/3x-ui` | Не относится к docbrain. |

### Сеть, тома, файлы

- Сеть: `home-codespaces_proxy` — единственная. Все новые сервисы цеплять к ней (`networks: [proxy]` + `name: proxy` в external или внутри корневого compose).
- Все persistent тома (`caddy_data`, `pgdata_provision`, `pgdata_scan`, `codeserver_*`, `authelia_redis_data`, …) — в корневом compose.
- Хост-файлы:
  - `/opt/home-codespaces/docker-compose.yml` — главный compose
  - `/opt/home-codespaces/Caddyfile` — read-only mount в caddy
  - `/opt/home-codespaces/.env` — общие секреты (DASHBOARD\_DATABASE\_URL, VAPID\_\*, TELEGRAM\_BOT\_TOKEN, MINIO\_\*, DB\_PROVISIONER\_API\_SECRET, PROVISION\_DB\_ADMIN\_PASSWORD, …)
  - Проекты code-server: `/opt/home-codespaces/projects/<name>/` (внутри code-server виден как `/home/coder/projects/<name>`).

---

## 2. Caddy — точка входа в HTTPS

Файл: `/opt/home-codespaces/Caddyfile`. Перезагрузка после правок:

```bash
docker exec home-codespaces-caddy-1 caddy reload --config /etc/caddy/Caddyfile
```

### Готовые snippet'ы

```caddy
# Защита через Authelia
(authelia) {
    forward_auth authelia:9091 {
        uri /api/authz/forward-auth
        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
    }
}

# Dev-порт code-server наружу (SPA + Authelia)
(devport) {
    import authelia
    reverse_proxy codeserver:{args[0]}
}
```

### Примеры существующих маршрутов (`Caddyfile`)

```caddy
scan.nikulshin-dev.online   { reverse_proxy dashboard:3000 }
code.nikulshin-dev.online   { reverse_proxy codeserver:8080 }
studio.nikulshin-dev.online { import devport 5555 }
db.nikulshin-dev.online {
    import authelia
    handle /api/* {
        reverse_proxy db-provisioner:8000 {
            header_up X-API-Key "<SECRET>"
        }
    }
    handle { reverse_proxy db-ui:80 }
}
```

### Что добавить для docbrain (план)

```caddy
docbrain.nikulshin-dev.online {
    # Webhook Telegram → FastAPI
    handle /tg/webhook* {
        reverse_proxy docbrain-backend:8000
    }
    # API для веб-чата и импорт от n8n
    handle /api/* {
        reverse_proxy docbrain-backend:8000
    }
    # Next.js фронт
    handle {
        reverse_proxy docbrain-web:3000
    }
}

# n8n за Authelia (НЕ публичный)
n8n.nikulshin-dev.online {
    import authelia
    reverse_proxy docbrain-n8n:5678
}
```

> Совет DeepSeek: Telegram-webhook должен быть **публично доступен без Authelia** (Telegram не умеет SSO). Делайте только префикс `/tg/webhook` без `import authelia`. Остальное API — либо публично с авторизацией на уровне FastAPI (JWT/API-key), либо тоже за Authelia в отдельном `handle`.

---

## 3. PostgreSQL + pgvector — критичная развилка

**Текущий `postgres-provision`** — `postgres:16-alpine`, **без расширения pgvector**:

```
docker exec postgres-provision psql -U admin -c \
  "SELECT name FROM pg_available_extensions WHERE name='vector';"
→ (0 rows)
```

### Варианты под docbrain (выбрать один)

1. **Заменить образ `postgres-provision` на `pgvector/pgvector:pg16`** (drop-in совместимый).
   - Плюс: одна БД на всё хозяйство, единый бэкап-пайплайн (cron 03:00 МСК → MinIO `db-backups`, ротация 7 дней).
   - Минус: миграция требует останова всех клиентов postgres-provision (scan-agent dashboard), при первом старте `CREATE EXTENSION vector;` в БД проекта. Volume `pgdata_provision` остаётся.
2. **Поднять отдельный `docbrain-db`** на образе `pgvector/pgvector:pg16` внутри `docbrain/docker-compose.yml`, изолированный том `pgdata_docbrain`.
   - Плюс: zero risk для scan-agent, миграции и бэкапы независимы.
   - Минус: ещё один Postgres-инстанс на хосте (≈ 30–80 МБ RAM idle), отдельный бэкап скрипт.

**Рекомендация:** для нового проекта — вариант 2 (изоляция). Если нужно унифицировать — потом мигрируем БД через `pg_dump` + `CREATE EXTENSION vector;`.

### Доступ к provisioner'у (если выбран вариант 1)

API `db.nikulshin-dev.online/api/databases` (POST с `{"name": "db_docbrain", "owner": "u_docbrain"}`), но **сначала** надо переключить образ на pgvector. Пароли владельцев попадают в `managed_databases` и доступны через UI.

---

## 4. Деплой через GHA → GHCR → webhook

**Шаблон деплоя scan-agent** (повторить для docbrain):

1. GHA билдит образы (`docbrain-backend`, `docbrain-web`) → пушит в GHCR `ghcr.io/dnikulshin/docbrain/{backend,web}:latest`.
2. GHA дёргает `https://webhook.nikulshin-dev.online/hooks/deploy-docbrain` с HMAC-секретом `WEBHOOK_SECRET_DOCBRAIN` (положить в `.env` и `webhook/hooks.json`).
3. Хук на VPS делает `docker compose pull docbrain-backend docbrain-web && docker compose up -d`.

Шаблоны хуков — в `/opt/home-codespaces/webhook/deploy-scan-agent.sh` и `hooks.json`.

---

## 5. Telegram, MinIO и прочие готовые секреты

В `/opt/home-codespaces/.env` уже лежат:

- `TELEGRAM_BOT_TOKEN` — токен бота (используется dashboard'ом scan-agent). **Для docbrain заведите отдельного бота** через @BotFather, переменная `DOCBRAIN_TELEGRAM_BOT_TOKEN`.
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` — админский доступ к MinIO. UI `minio.nikulshin-dev.ru`, S3 endpoint `s3.nikulshin-dev.ru`. Удобно для хранения загруженных пользователем файлов до обработки, либо для бэкапов pgvector.
- `DB_PROVISIONER_API_SECRET` — если решите ходить через provisioner.

> ⚠️ Все секреты — только маскированно в чат. Никогда не печатать значения.

---

## 6. n8n — где и как поднять

В текущем стеке n8n **нет**. Для docbrain:

```yaml
docbrain-n8n:
  image: n8nio/n8n:latest
  restart: unless-stopped
  environment:
    - N8N_HOST=n8n.nikulshin-dev.online
    - N8N_PROTOCOL=https
    - WEBHOOK_URL=https://n8n.nikulshin-dev.online/
    - GENERIC_TIMEZONE=Europe/Moscow
    # Auth выключаем — будет Authelia на Caddy-уровне
    - N8N_BASIC_AUTH_ACTIVE=false
  volumes:
    - n8n_data:/home/node/.n8n
  networks: [proxy]
```

Google Drive credentials — внутри n8n через OAuth2-узел (creds хранятся в `~/.n8n` томе, ключ шифрования из `N8N_ENCRYPTION_KEY` в `.env`).

---

## 7. Что от меня (Кодера) можно ожидать в этой среде

Я работаю **внутри code-server-контейнера**, но `/var/run/docker.sock` примонтирован — поэтому могу:

- `docker ps / exec / inspect` против любых VPS-контейнеров;
- читать/писать `/opt/home-codespaces/*` через одноразовый `alpine` контейнер с маунтом;
- запускать `docker compose` через образ `docker:cli`:
  ```
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v /opt/home-codespaces:/work -w /work docker:cli compose <cmd>
  ```
- править Caddyfile + reload caddy, добавлять переменные в `.env`, заводить новые контейнеры в корневом compose **или** в отдельном `/home/coder/projects/docbrain/docker-compose.yml` (последний удобнее для изоляции, цепляется к сети `home-codespaces_proxy` как external).

Чего я **не** делаю автоматом: не пушу секреты в чат, не сношу чужие тома, не трогаю `portfolio-next-*` и `3xui-*`.

---

## 8. Предлагаемая структура `docbrain/` (черновик)

```
/home/coder/projects/docbrain/
├── docker-compose.yml          # docbrain-backend, docbrain-web, docbrain-db, docbrain-n8n
├── backend/                    # FastAPI + RAG + function-calling agent
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── app/
├── web/                        # Next.js 15 (App Router)
│   ├── Dockerfile
│   └── ...
├── n8n/                        # экспорт workflow JSON для версионирования
└── INFRA.md                    # ← этот файл
```

Стандартный путь: каждый сервис билдится локально или тянется из GHCR, цепляется к сети `home-codespaces_proxy` (external), Caddy на хосте уже знает про сабдомены.

---

## 9. Open questions для DeepSeek

1. **pgvector**: вариант 1 (общий postgres-provision на pgvector-образе) или вариант 2 (отдельный `docbrain-db`)?
2. **Auth для веб-чата**: Authelia (SSO, удобно, но Telegram-бот всё равно идентифицирует юзеров по chat_id) или собственный JWT-логин в FastAPI?
3. **OpenRouter ключ**: один на сервис (в `.env` контейнера) или по-юзерски (мульти-тенант)?
4. **n8n импорт**: pull-mode по cron каждые 6ч **или** push-mode из Google Drive webhook → n8n?
5. **Хранение исходников файлов**: оставлять в MinIO (S3) или только эмбеддинги в pgvector?
