"""mark existing indexed documents ready

Revision ID: 4e73187f2a3d
Revises: 2b15e47b239a
Create Date: 2026-11-01 04:19:11.725743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e73187f2a3d'
down_revision: Union[str, Sequence[str], None] = '2b15e47b239a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE documents
        SET status = 'ready'
        WHERE EXISTS (
            SELECT 1
            FROM document_chunks
            WHERE document_chunks.document_id = documents.id
        )
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE documents
        SET status = 'queued'
        WHERE status = 'ready'
    """)
