"""add visitor_identified to lead_source

sales_ai_service's save_contact_info (and its deterministic capture
backstop) now creates a Lead the moment a visitor's name/email/phone is
saved, even with no buying intent — not just via request_sales_contact.
This gives that path its own LeadSource value rather than overloading an
existing one (e.g. MANUAL, which means something different — a lead
entered by staff).

Revision ID: 0008_lead_source_visitor_id
Revises: 0007_visitor_identified
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008_lead_source_visitor_id"
down_revision: Union[str, None] = "0007_visitor_identified"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lead_source ADD VALUE IF NOT EXISTS 'visitor_identified'")


def downgrade() -> None:
    # Postgres does not support removing a value from an enum type.
    pass
