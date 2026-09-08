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
