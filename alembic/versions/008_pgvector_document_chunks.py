"""pgvector column for document_chunks (RAG / LLM-203)

Revision ID: 008
Revises: 007
Create Date: 2026-04-06

"""

from typing import Sequence, Union

from alembic import op

from citycouncil.constants import PGVECTOR_EMBEDDING_DIMENSION

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    dim = PGVECTOR_EMBEDDING_DIMENSION
    op.execute(f"ALTER TABLE document_chunks ADD COLUMN embedding_vector vector({dim})")
    op.execute(
        f"""
        UPDATE document_chunks
        SET embedding_vector = ('[' || array_to_string(embedding, ',') || ']')::vector
        WHERE embedding IS NOT NULL
          AND array_length(embedding, 1) = {dim}
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_vector")
