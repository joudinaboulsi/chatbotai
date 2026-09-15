"""add channel to agents

Revision ID: 0d1d9462aad6
Revises: a8a07ca2d401
Create Date: 2026-09-14 11:10:47.528680

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0d1d9462aad6'
down_revision: Union[str, None] = 'a8a07ca2d401'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

agent_channel = sa.Enum('web', 'whatsapp', name='agent_channel')


def upgrade() -> None:
    agent_channel.create(op.get_bind())
    op.add_column(
        'agents',
        sa.Column('channel', agent_channel, nullable=False, server_default='web'),
    )
    op.alter_column('agents', 'channel', server_default=None)


def downgrade() -> None:
    op.drop_column('agents', 'channel')
    agent_channel.drop(op.get_bind())
