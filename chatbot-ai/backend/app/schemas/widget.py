import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ConversationStatus, MessageSender, WidgetPosition, WidgetSize


class WidgetConfigOut(BaseModel):
    agent_id: uuid.UUID
    company_name: str
    agent_name: str
    logo_url: str | None
    avatar_url: str | None
    primary_color: str
    secondary_color: str
    background_color: str
    text_color: str
    button_color: str
    font_family: str
    font_size: str
    widget_position: WidgetPosition
    widget_size: WidgetSize
    welcome_message: str
    placeholder_text: str


class MessageOut(BaseModel):
    id: uuid.UUID
    sender_type: MessageSender
    content: str
    message_metadata: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionRequest(BaseModel):
    session_token: str | None = None
    login_token: str | None = None


class SessionResponse(BaseModel):
    session_token: str
    conversation_id: uuid.UUID
    conversation_status: ConversationStatus
    messages: list[MessageOut]


class MessagesSinceResponse(BaseModel):
    conversation_status: ConversationStatus
    messages: list[MessageOut]


class SendMessageRequest(BaseModel):
    session_token: str
    message: str = Field(min_length=1, max_length=4000)
    quick_reply: str | None = None


class SendMessageResponse(BaseModel):
    conversation_status: ConversationStatus
    messages: list[MessageOut]


class VisitorUpdateRequest(BaseModel):
    session_token: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None


class LeadRequest(BaseModel):
    session_token: str
    source: str | None = None


class HandoffRequest(BaseModel):
    session_token: str
    accepted: bool
