import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import LiveAgentRequestStatus


class LiveAgentRequestOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    visitor_id: uuid.UUID
    agent_id: uuid.UUID
    status: LiveAgentRequestStatus
    assigned_operator_id: uuid.UUID | None
    requested_at: datetime
    assigned_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}
