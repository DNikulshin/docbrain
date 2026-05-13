"""documents and chunks tables

Revision ID: 0002_documents_and_chunks
Revises: 0001_enable_pgvector
Create Date: 2026-05-13

Создаёт таблицы documents и chunks с типом vector(1536), FK с ON DELETE CASCADE,
уникальностью (document_id, ord) и HNSW-индексом по embedding под cosine.
Размерность 1536 — литерал; миграции не зависят от рантайм-конфига.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_documents_and_chunks"
down_revision: str | Sequence[str] | None = "0001_enable_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE documents (
            id           uuid        PRIMARY KEY,
            name         text        NOT NULL,
            content_type text        NOT NULL,
            source       text        NULL,
            created_at   timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE chunks (
            id          uuid        PRIMARY KEY,
            document_id uuid        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            ord         integer     NOT NULL,
            text        text        NOT NULL,
            embedding   vector(1536) NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_chunks_doc_ord UNIQUE (document_id, ord)
        )
        """
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw "
        "ON chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunks")
    op.execute("DROP TABLE IF EXISTS documents")
