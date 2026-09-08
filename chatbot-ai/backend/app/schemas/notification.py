import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import NotificationType


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    body: str | None
    resource_type: str | None
    resource_id: uuid.UUID | None
    link: str | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
