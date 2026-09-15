"""add visitor_identified to notification_type

Lighter-weight companion to NEW_LEAD: fires the first time a previously
fully-anonymous visitor gets a name/email/phone saved (via
sales_ai_service's save_contact_info tool or its deterministic capture
backstop), even with no buying intent yet — so staff see engaged
visitors sooner instead of only once a real Lead exists.

Revision ID: 0007_visitor_identified
Revises: 0006_visitor_sales_profile
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007_visitor_identified"
down_revision: Union[str, None] = "0006_visitor_sales_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'visitor_identified'")


def downgrade() -> None:
    # Postgres does not support removing a value from an enum type.
    pass
