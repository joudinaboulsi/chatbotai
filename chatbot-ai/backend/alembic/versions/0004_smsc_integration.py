"""add smsc integration tables

Revision ID: 0004_smsc_integration
Revises: 0003_agent_remarks
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_smsc_integration"
down_revision: Union[str, None] = "0003_agent_remarks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "smsc_settings",
        _uuid_pk(),
        sa.Column("enabled", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("api_base_url", sa.String(500)),
        sa.Column("api_key_encrypted", sa.String(1024)),
        sa.Column(
            "auth_scheme", sa.Enum("api_key", "bearer", name="smsc_auth_scheme"), server_default="bearer", nullable=False
        ),
        sa.Column("timeout_seconds", sa.Integer, server_default="10", nullable=False),
        sa.Column("session_expire_minutes", sa.Integer, server_default="30", nullable=False),
        sa.Column("is_configured", sa.Boolean, server_default=sa.false(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "smsc_sessions",
        _uuid_pk(),
        sa.Column(
            "conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "visitor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_token", sa.String(64), nullable=False, unique=True),
        sa.Column("smsc_user_id", sa.String(255)),
        sa.Column("username", sa.String(255)),
        sa.Column(
            "status",
            sa.Enum("pending", "authenticated", "expired", "terminated", name="smsc_session_status"),
            server_default="pending",
            nullable=False,
        ),
        
        sa.Column("pending_question", sa.Text),
        sa.Column("failed_attempts", sa.Integer, server_default="0", nullable=False),
        sa.Column("authenticated_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("conversation_id", name="uq_smsc_session_conversation"),
    )

    op.create_table(
        "smsc_api_logs",
        _uuid_pk(),
        sa.Column(
            "conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")
        ),
        sa.Column("smsc_user_id", sa.String(255)),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("request_type", sa.String(10), nullable=False),
        sa.Column("response_status", sa.Integer),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("error_message", sa.String(500)),
        *_timestamps(),
    )
    
    op.create_index("ix_smsc_api_logs_conversation_id", "smsc_api_logs", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_smsc_api_logs_conversation_id", table_name="smsc_api_logs")
    op.drop_table("smsc_api_logs")
    op.drop_table("smsc_sessions")
    op.drop_table("smsc_settings")
    op.execute("DROP TYPE IF EXISTS smsc_session_status")
    op.execute("DROP TYPE IF EXISTS smsc_auth_scheme")
