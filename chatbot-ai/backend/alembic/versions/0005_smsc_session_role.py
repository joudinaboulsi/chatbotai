"""add role to smsc_sessions

The SMSC webapp now has two roles: "support" (staff who diagnose any
user's traffic) and "user" (a tenant who asks about their own account).
The role comes back from the SMSC API's validate-user / exchange-widget-
token responses and is stored here so smsc_ai_service can offer a
different tool set / system prompt per role without an extra API call on
every turn.

Revision ID: 0005_smsc_session_role
Revises: 0004_smsc_integration
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_smsc_session_role"
down_revision: Union[str, None] = "0004_smsc_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("smsc_sessions", sa.Column("role", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("smsc_sessions", "role")
