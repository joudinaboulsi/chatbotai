"""add archived_at to leads

Revision ID: 2007f60cdc51
Revises: 0008_lead_source_visitor_id
Create Date: 2026-09-14 09:20:29.675196

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '2007f60cdc51'
down_revision: Union[str, None] = '0008_lead_source_visitor_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'archived_at')
