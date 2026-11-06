
"""add full text search to document chunks

Revision ID: 9982ab9eda35
Revises: 5e4a164b98f5
Create Date: 2026-11-06 06:19:27.104424

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9982ab9eda35"
down_revision: Union[str, Sequence[str], None] = "5e4a164b98f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add PostgreSQL full-text search support."""

    # Add a generated tsvector column derived from chunk_text.
    op.execute("""
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english', chunk_text)
        ) STORED;
    """)

    # Create a GIN index for efficient full-text searches.
    op.execute("""
        CREATE INDEX idx_document_chunks_search_vector
        ON document_chunks
        USING GIN (search_vector);
    """)


def downgrade() -> None:
    """Remove PostgreSQL full-text search support."""

    op.execute("""
        DROP INDEX IF EXISTS idx_document_chunks_search_vector;
    """)

    op.execute("""
        ALTER TABLE document_chunks
        DROP COLUMN IF EXISTS search_vector;
    """)
