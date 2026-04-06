"""pgvector column for document_chunks (RAG / LLM-203)

Revision ID: 008
Revises: 007
Create Date: 2026-04-06

"""

from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match default CITYCOUNCIL_EMBEDDING_DIMENSIONS (384) for HNSW + embed_jobs sync.
PGVECTOR_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"ALTER TABLE document_chunks ADD COLUMN embedding_vector vector({PGVECTOR_DIM})")
    op.execute(
        """
        UPDATE document_chunks
        SET embedding_vector = ('[' || array_to_string(embedding, ',') || ']')::vector
        WHERE embedding IS NOT NULL
          AND array_length(embedding, 1) = 384
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_vector")
