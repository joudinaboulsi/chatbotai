import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import LeadSource, LeadStatus


class LeadOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    visitor_id: uuid.UUID
    conversation_id: uuid.UUID
    name: str | None
    email: str | None
    phone: str | None
    company: str | None
    source: LeadSource
    status: LeadStatus
    assigned_operator_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class LeadUpdate(BaseModel):
    status: LeadStatus | None = None
    assigned_operator_id: uuid.UUID | None = None
    notes: str | None = None
    company: str | None = None


class PaginatedLeads(BaseModel):
    items: list[LeadOut]
    total: int
    page: int
    page_size: int
    # Counts per status across the whole (role/agent/archived-scoped) lead
    # set, ignoring the current status filter — mirrors
    # PaginatedConversations.status_counts so the tab counts stay stable
    # as the user filters rather than shrinking to match the active view.
    status_counts: dict[str, int]
