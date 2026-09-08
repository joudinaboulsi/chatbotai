import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum
from app.models.enums import KnowledgeSourceType, ProcessingStatus, ScrapeMode

_knowledge_source_type_enum = pg_enum(KnowledgeSourceType, "knowledge_source_type")

agent_knowledge_bases = Table(
    "agent_knowledge_bases",
    Base.metadata,
    Column("agent_id", UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
    Column("knowledge_base_id", UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), primary_key=True),
)


class KnowledgeBase(Base, UUIDPKMixin, TimestampMixin):
    """A named collection of knowledge sources (PDFs and/or scraped sites),
    assignable to one or more Agents (many-to-many)."""

    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Fixed at creation and enforced server-side (see routes) — a knowledge
    # base is exclusively a PDF collection or a website collection, never
    # both, so the admin UI never has to guess which section to show.
    source_type: Mapped[KnowledgeSourceType] = mapped_column(_knowledge_source_type_enum, nullable=False)

    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    scraped_sites: Mapped[list["ScrapedSite"]] = relationship(
        back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    agents: Mapped[list["Agent"]] = relationship(secondary=agent_knowledge_bases, backref="knowledge_bases")


class KnowledgeDocument(Base, UUIDPKMixin, TimestampMixin):
    """An uploaded PDF source within a knowledge base."""

    __tablename__ = "knowledge_documents"

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ProcessingStatus] = mapped_column(
        pg_enum(ProcessingStatus, "processing_status"), default=ProcessingStatus.PENDING, nullable=False
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ScrapedSite(Base, UUIDPKMixin, TimestampMixin):
    """A website scraping/crawling job configuration + status within a
    knowledge base."""

    __tablename__ = "scraped_sites"

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    mode: Mapped[ScrapeMode] = mapped_column(
        pg_enum(ScrapeMode, "scrape_mode"), default=ScrapeMode.SINGLE_URL, nullable=False
    )
    max_pages: Mapped[int] = mapped_column(Integer, default=20)
    max_depth: Mapped[int] = mapped_column(Integer, default=2)
    include_subpages: Mapped[bool] = mapped_column(default=True)
    exclude_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    status: Mapped[ProcessingStatus] = mapped_column(
        pg_enum(ProcessingStatus, "processing_status"), default=ProcessingStatus.PENDING, nullable=False
    )
    pages_discovered: Mapped[int] = mapped_column(Integer, default=0)
    pages_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="scraped_sites")
    pages: Mapped[list["ScrapedPage"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )


class ScrapedPage(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "scraped_pages"

    scraped_site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraped_sites.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[ProcessingStatus] = mapped_column(
        pg_enum(ProcessingStatus, "processing_status"), default=ProcessingStatus.PENDING, nullable=False
    )
    content_hash: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)

    site: Mapped["ScrapedSite"] = relationship(back_populates="pages")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="scraped_page", cascade="all, delete-orphan"
    )


class KnowledgeChunk(Base, UUIDPKMixin, TimestampMixin):
    """A single embedded text chunk used for RAG retrieval. Belongs to
    exactly one of (document, scraped_page)."""

    __tablename__ = "knowledge_chunks"

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE")
    )
    scraped_page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraped_pages.id", ondelete="CASCADE")
    )
    source_type: Mapped[KnowledgeSourceType] = mapped_column(
        pg_enum(KnowledgeSourceType, "knowledge_source_type"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.OPENAI_EMBEDDING_DIMENSIONS))
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    document: Mapped["KnowledgeDocument | None"] = relationship(back_populates="chunks")
    scraped_page: Mapped["ScrapedPage | None"] = relationship(back_populates="chunks")
