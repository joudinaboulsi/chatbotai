import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import AgentChannel, AgentStatus, WidgetPosition, WidgetSize


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    description: str | None = None
    remarks: str | None = None
    languages: list[str] = Field(default_factory=lambda: ["en"])
    notification_email: EmailStr | None = None
    channel: AgentChannel = AgentChannel.WEB


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    description: str | None = None
    remarks: str | None = None
    languages: list[str] | None = None
    notification_email: EmailStr | None = None


class AgentOut(BaseModel):
    id: uuid.UUID
    name: str
    company_name: str
    industry: str | None
    description: str | None
    remarks: str | None
    languages: list[str]
    status: AgentStatus
    channel: AgentChannel
    notification_email: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentListItem(BaseModel):
    id: uuid.UUID
    name: str
    company_name: str
    industry: str | None
    languages: list[str]
    status: AgentStatus
    channel: AgentChannel
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedAgents(BaseModel):
    items: list[AgentListItem]
    total: int
    page: int
    page_size: int


class BrandingUpdate(BaseModel):
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    button_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family: str | None = Field(default=None, max_length=100)
    font_size: str | None = Field(default=None, max_length=20)
    widget_position: WidgetPosition | None = None
    widget_size: WidgetSize | None = None
    welcome_message: str | None = Field(default=None, max_length=2000)
    placeholder_text: str | None = Field(default=None, max_length=255)
    display_company_name: str | None = Field(default=None, max_length=255)
    display_agent_name: str | None = Field(default=None, max_length=255)


class BrandingOut(BaseModel):
    agent_id: uuid.UUID
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
    display_company_name: str | None
    display_agent_name: str | None

    model_config = {"from_attributes": True}
