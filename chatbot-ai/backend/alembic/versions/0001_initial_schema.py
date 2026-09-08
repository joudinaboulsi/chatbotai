"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
 
EMBEDDING_DIM = 1536


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "email_settings",
        _uuid_pk(),
        sa.Column("smtp_host", sa.String(255)),
        sa.Column("smtp_port", sa.Integer, server_default="587"),
        sa.Column("smtp_username", sa.String(255)),
        sa.Column("smtp_password_encrypted", sa.String(1024)),
        sa.Column(
            "encryption",
            sa.Enum("none", "ssl", "tls", name="smtp_encryption"),
            server_default="tls",
            nullable=False,
        ),
        sa.Column("from_name", sa.String(255)),
        sa.Column("from_email", sa.String(255)),
        sa.Column("support_email", sa.String(255)),
        sa.Column("is_configured", sa.Boolean, server_default=sa.false(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "knowledge_bases",
        _uuid_pk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        *_timestamps(),
    )

    op.create_table(
        "roles",
        _uuid_pk(),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(255)),
    )

    op.create_table(
        "knowledge_documents",
        _uuid_pk(),
        sa.Column(
            "knowledge_base_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="processing_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_knowledge_documents_kb_id", "knowledge_documents", ["knowledge_base_id"])

    op.create_table(
        "scraped_sites",
        _uuid_pk(),
        sa.Column(
            "knowledge_base_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column(
            "mode", sa.Enum("single_url", "crawl", name="scrape_mode"), server_default="single_url", nullable=False
        ),
        sa.Column("max_pages", sa.Integer, server_default="20"),
        sa.Column("max_depth", sa.Integer, server_default="2"),
        sa.Column("include_subpages", sa.Boolean, server_default=sa.true()),
        sa.Column("exclude_urls", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "processing", "completed", "failed", name="processing_status", create_type=False
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("pages_discovered", sa.Integer, server_default="0"),
        sa.Column("pages_processed", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_scraped_sites_kb_id", "scraped_sites", ["knowledge_base_id"])

    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column(
            "status", sa.Enum("active", "inactive", name="active_status"), server_default="active", nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "agents",
        _uuid_pk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("languages", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column(
            "status",
            postgresql.ENUM("active", "inactive", name="active_status", create_type=False),
            server_default="active",
            nullable=False,
        ),
        sa.Column("notification_email", sa.String(255)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        *_timestamps(),
    )
    op.create_index("ix_agents_status", "agents", ["status"])

    op.create_table(
        "audit_logs",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("details", postgresql.JSONB, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "scraped_pages",
        _uuid_pk(),
        sa.Column(
            "scraped_site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scraped_sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "processing", "completed", "failed", name="processing_status", create_type=False
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("error_message", sa.Text),
        *_timestamps(),
    )
    op.create_index("ix_scraped_pages_site_id", "scraped_pages", ["scraped_site_id"])

    op.create_table(
        "agent_branding",
        _uuid_pk(),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("logo_url", sa.String(1024)),
        sa.Column("avatar_url", sa.String(1024)),
        sa.Column("primary_color", sa.String(9), server_default="#0066A1"),
        sa.Column("secondary_color", sa.String(9), server_default="#003D63"),
        sa.Column("background_color", sa.String(9), server_default="#FFFFFF"),
        sa.Column("text_color", sa.String(9), server_default="#1A1A1A"),
        sa.Column("button_color", sa.String(9), server_default="#0066A1"),
        sa.Column("font_family", sa.String(100), server_default="Inter"),
        sa.Column("font_size", sa.String(20), server_default="14px"),
        sa.Column(
            "widget_position",
            sa.Enum("bottom_right", "bottom_left", name="widget_position"),
            server_default="bottom_right",
        ),
        
        sa.Column(
            "widget_size",
            sa.Enum("standard", "compact", "large", name="widget_size"),
            server_default="standard",
        ),
        sa.Column(
            "welcome_message",
            sa.Text,
            server_default="Hello! I'm here to help. How can I assist you today?",
        ),
        sa.Column("placeholder_text", sa.String(255), server_default="Type your message..."),
        sa.Column("display_company_name", sa.String(255)),
        sa.Column("display_agent_name", sa.String(255)),
        *_timestamps(),
    )

    op.create_table(
        "agent_knowledge_bases",
        sa.Column(
            "agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "knowledge_base_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "knowledge_chunks",
        _uuid_pk(),
        sa.Column(
            "knowledge_base_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE")
        ),
        sa.Column(
            "scraped_page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scraped_pages.id", ondelete="CASCADE")
        ),
        sa.Column("source_type", sa.Enum("pdf", "website", name="knowledge_source_type"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, server_default="0"),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("chunk_metadata", postgresql.JSONB, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_knowledge_chunks_kb_id", "knowledge_chunks", ["knowledge_base_id"])
    # ANN index for cosine similarity search. ivfflat requires rows to exist
    # for a meaningful `lists` value at higher scale; fine to create empty.
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding ON knowledge_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "notifications",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE")),
        sa.Column(
            "type",
            sa.Enum(
                "new_lead",
                "live_agent_request",
                "new_conversation",
                "kb_processing_failed",
                "email_failed",
                "system_error",
                name="notification_type",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("link", sa.String(500)),
        sa.Column("is_read", sa.Boolean, server_default=sa.false(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    op.create_table(
        "operator_assignments",
        _uuid_pk(),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "agent_id", name="uq_operator_agent"),
    )

    op.create_table(
        "visitors",
        _uuid_pk(),
        sa.Column(
            "agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("session_token", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp()),
        *_timestamps(),
    )
    op.create_index("ix_visitors_session_token", "visitors", ["session_token"])
    op.create_index("ix_visitors_agent_id", "visitors", ["agent_id"])

    op.create_table(
        "conversations",
        _uuid_pk(),
        sa.Column(
            "agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "visitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ai_active",
                "waiting_for_agent",
                "human_active",
                "resolved",
                "closed",
                name="conversation_status",
            ),
            server_default="ai_active",
            nullable=False,
        ),
        sa.Column(
            "assigned_operator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp()),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_conversations_agent_status", "conversations", ["agent_id", "status"])
    op.create_index("ix_conversations_visitor_id", "conversations", ["visitor_id"])

    op.create_table(
        "leads",
        _uuid_pk(),
        sa.Column(
            "agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "visitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("company", sa.String(255)),
        sa.Column(
            "source",
            sa.Enum(
                "pricing_request",
                "demo_request",
                "quote_request",
                "purchase_request",
                "service_inquiry",
                "contact_sales_request",
                "human_support_request",
                "manual",
                name="lead_source",
            ),
            server_default="manual",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("new", "contacted", "qualified", "converted", "closed", name="lead_status"),
            server_default="new",
            nullable=False,
        ),
        sa.Column(
            "assigned_operator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("notes", sa.Text),
        *_timestamps(),
        sa.UniqueConstraint("conversation_id", name="uq_lead_conversation"),
    )
    op.create_index("ix_leads_agent_status", "leads", ["agent_id", "status"])

    op.create_table(
        "live_agent_requests",
        _uuid_pk(),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "visitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum("waiting", "assigned", "active", "resolved", "closed", name="live_agent_request_status"),
            server_default="waiting",
            nullable=False,
        ),
        sa.Column(
            "assigned_operator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_live_agent_requests_status", "live_agent_requests", ["status"])

    op.create_table(
        "messages",
        _uuid_pk(),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_type", sa.Enum("visitor", "ai", "operator", "system", name="message_sender"), nullable=False),
        sa.Column(
            "sender_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("message_metadata", postgresql.JSONB, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("live_agent_requests")
    op.drop_table("leads")
    op.drop_table("conversations")
    op.drop_table("visitors")
    op.drop_table("operator_assignments")
    op.drop_table("notifications")
    op.drop_table("knowledge_chunks")
    op.drop_table("agent_knowledge_bases")
    op.drop_table("agent_branding")
    op.drop_table("scraped_pages")
    op.drop_table("audit_logs")
    op.drop_table("agents")
    op.drop_table("users")
    op.drop_table("scraped_sites")
    op.drop_table("knowledge_documents")
    op.drop_table("roles")
    op.drop_table("knowledge_bases")
    op.drop_table("email_settings")

    for enum_name in (
        "smtp_encryption",
        "processing_status",
        "active_status",
        "widget_position",
        "widget_size",
        "knowledge_source_type",
        "scrape_mode",
        "notification_type",
        "conversation_status",
        "lead_source",
        "lead_status",
        "live_agent_request_status",
        "message_sender",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    op.execute("DROP EXTENSION IF EXISTS vector")
