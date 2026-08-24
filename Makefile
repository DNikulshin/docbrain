.PHONY: help install lint format test migrate run

help:
	@echo "Available commands:"
	@echo "  install    - Install backend dependencies"
	@echo "  lint       - Run ruff check"
	@echo "  format     - Run ruff format"
	@echo "  test       - Run pytest"
	@echo "  migrate    - Apply alembic migrations"
	@echo "  run        - Run uvicorn dev server"

install:
	cd backend && pip install -r requirements.txt -r requirements-dev.txt

lint:
	cd backend && ruff check .

format:
	cd backend && ruff format .

test:
	cd backend && pytest -v

migrate:
	cd backend && alembic upgrade head

run:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000