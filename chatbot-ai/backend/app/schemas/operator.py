import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole, UserStatus


class OperatorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: UserRole
    assigned_agent_ids: list[uuid.UUID] = Field(default_factory=list)


class OperatorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    status: UserStatus | None = None
    assigned_agent_ids: list[uuid.UUID] | None = None


class OperatorOut(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole
    status: UserStatus
    assigned_agent_ids: list[uuid.UUID]
    last_login_at: datetime | None
    created_at: datetime
