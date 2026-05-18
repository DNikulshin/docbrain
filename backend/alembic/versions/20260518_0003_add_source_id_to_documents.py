"""add source_id to documents

Revision ID: 0003_add_source_id_to_documents
Revises: 0002_documents_and_chunks
Create Date: 2026-05-18

Добавляет колонку source_id (nullable, unique) в таблицу documents.
Используется для дедупликации при импорте из внешних источников (Google Drive).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_source_id_to_documents"
down_revision: str | Sequence[str] | None = "0002_documents_and_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_id", sa.String(), nullable=True))
    op.create_index("ix_documents_source_id", "documents", ["source_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_documents_source_id", table_name="documents")
    op.drop_column("documents", "source_id")
