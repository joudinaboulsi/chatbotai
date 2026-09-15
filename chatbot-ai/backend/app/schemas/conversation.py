import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ConversationStatus, MessageSender


class MessageOut(BaseModel):
    id: uuid.UUID
    sender_type: MessageSender
    sender_user_id: uuid.UUID | None
    content: str
    message_metadata: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    visitor_name: str | None
    visitor_email: str | None
    visitor_phone: str | None
    status: ConversationStatus
    assigned_operator_id: uuid.UUID | None
    started_at: datetime
    last_message_at: datetime | None
    message_count: int
    last_message_preview: str | None
    archived_at: datetime | None


class ConversationDetail(ConversationListItem):
    messages: list[MessageOut]


class PaginatedConversations(BaseModel):
    items: list[ConversationListItem]
    total: int
    page: int
    page_size: int
    # Counts per status across the whole (role/agent-scoped) conversation
    # set, ignoring the current status/has_lead/search filters — this is
    # what drives the tab and stat-card counts, which should stay stable
    # as the user filters rather than shrinking to match the active view.
    status_counts: dict[str, int]


class SendOperatorMessageRequest(BaseModel):
    content: str


class WhatsAppReplyRequest(BaseModel):
    text: str
