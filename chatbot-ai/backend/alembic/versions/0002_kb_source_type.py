"""add source_type to knowledge_bases

Revision ID: 0002_kb_source_type
Revises: 0001_initial_schema
Create Date: 2026-09-03

"""
from typing import Sequence, Union
 
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_kb_source_type"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # knowledge_source_type already exists (created alongside knowledge_chunks
    # in 0001) — reuse it rather than creating a duplicate PG enum type.
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "source_type",
            postgresql.ENUM("pdf", "website", name="knowledge_source_type", create_type=False),
            nullable=False,
            server_default="pdf",
        ),
    )
    op.alter_column("knowledge_bases", "source_type", server_default=None)


def downgrade() -> None:
    op.drop_column("knowledge_bases", "source_type")
