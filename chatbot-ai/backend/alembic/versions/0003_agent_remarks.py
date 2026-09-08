"""add remarks to agents

Revision ID: 0003_agent_remarks
Revises: 0002_kb_source_type
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_agent_remarks"
down_revision: Union[str, None] = "0002_kb_source_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("remarks", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "remarks")
