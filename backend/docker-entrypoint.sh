#!/bin/sh
# Применяем миграции перед стартом приложения. БД уже здорова благодаря
# depends_on: condition: service_healthy в docker-compose.
set -e

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] exec $*"
exec "$@"
