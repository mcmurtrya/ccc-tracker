"""Shared constants (keep in sync with Alembic pgvector migration)."""

from typing import Final

# Fixed pgvector column width; must match Alembic ``document_chunks.embedding_vector`` and
# :attr:`~citycouncil.config.Settings.embedding_dimensions` default.
PGVECTOR_EMBEDDING_DIMENSION: Final[int] = 384
