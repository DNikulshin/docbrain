"""enable pgvector extension

Revision ID: 0001_enable_pgvector
Revises:
Create Date: 2026-05-13

Базовая миграция: включаем расширение vector в БД docbrain. Должна быть
первой — все RAG-таблицы с типом vector(N) опираются на это расширение.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_pgvector"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
