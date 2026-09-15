"""add archived_at to conversations

Revision ID: a8a07ca2d401
Revises: 2007f60cdc51
Create Date: 2026-09-14 09:28:38.069736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a8a07ca2d401'
down_revision: Union[str, None] = '2007f60cdc51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('conversations', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('conversations', 'archived_at')
