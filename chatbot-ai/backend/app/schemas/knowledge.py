import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.models.enums import KnowledgeSourceType, ProcessingStatus, ScrapeMode


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    source_type: KnowledgeSourceType
    agent_ids: list[uuid.UUID] = Field(default_factory=list)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    agent_ids: list[uuid.UUID] | None = None


class KnowledgeBaseOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    source_type: KnowledgeSourceType
    agent_ids: list[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, kb) -> "KnowledgeBaseOut":
        return cls(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            source_type=kb.source_type,
            agent_ids=[a.id for a in kb.agents],
            created_at=kb.created_at,
        )


class KnowledgeDocumentOut(BaseModel):
    id: uuid.UUID
    file_name: str
    file_size_bytes: int
    status: ProcessingStatus
    chunk_count: int
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class ScrapeRequest(BaseModel):
    url: HttpUrl
    mode: ScrapeMode = ScrapeMode.SINGLE_URL
    max_pages: int = Field(default=20, ge=1, le=500)
    max_depth: int = Field(default=2, ge=1, le=5)
    include_subpages: bool = True
    exclude_urls: list[str] = Field(default_factory=list)


class ScrapedSiteOut(BaseModel):
    id: uuid.UUID
    base_url: str
    mode: ScrapeMode
    max_pages: int
    max_depth: int
    include_subpages: bool
    exclude_urls: list[str]
    status: ProcessingStatus
    pages_discovered: int
    pages_processed: int
    error_message: str | None
    last_scraped_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
