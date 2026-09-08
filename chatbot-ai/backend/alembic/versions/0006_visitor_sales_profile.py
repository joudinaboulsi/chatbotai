"""add sales_profile to visitors

The public sales chatbot flow (see app.services.sales_flow_service)
collects business type, use case, monthly SMS volume, destination
countries, and integration status from a prospect before recommending a
package. Stored as one JSON blob rather than a column per field since the
question set is expected to keep evolving.

Revision ID: 0006_visitor_sales_profile
Revises: 0005_smsc_session_role
Create Date: 2026-09-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_visitor_sales_profile"
down_revision: Union[str, None] = "0005_smsc_session_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "visitors",
        sa.Column("sales_profile", postgresql.JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("visitors", "sales_profile")
