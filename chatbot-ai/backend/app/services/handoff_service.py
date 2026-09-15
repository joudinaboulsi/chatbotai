import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.conversation import Conversation, Visitor
from app.models.enums import (
    ConversationStatus,
    LeadSource,
    LiveAgentRequestStatus,
    NotificationType,
)
from app.models.live_agent import LiveAgentRequest
from app.services import email_service
from app.services.lead_service import create_or_get_lead
from app.services.notification_service import notify

logger = logging.getLogger("app.handoff")

_ACTIVE_STATUSES = (LiveAgentRequestStatus.WAITING, LiveAgentRequestStatus.ASSIGNED, LiveAgentRequestStatus.ACTIVE)


async def get_active_request(db: AsyncSession, conversation_id: uuid.UUID) -> LiveAgentRequest | None:
    result = await db.execute(
        select(LiveAgentRequest).where(
            LiveAgentRequest.conversation_id == conversation_id,
            LiveAgentRequest.status.in_(_ACTIVE_STATUSES),
        )
    )
    return result.scalar_one_or_none()


async def request_handoff(
    db: AsyncSession, *, agent: Agent, visitor: Visitor, conversation: Conversation, reason: str | None = None
) -> LiveAgentRequest:
    existing = await get_active_request(db, conversation.id)
    if existing is not None:
        return existing

    request = LiveAgentRequest(
        conversation_id=conversation.id,
        visitor_id=visitor.id,
        agent_id=agent.id,
        status=LiveAgentRequestStatus.WAITING,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(request)
    conversation.status = ConversationStatus.WAITING_FOR_AGENT
    await db.flush()

    await create_or_get_lead(
        db, agent=agent, visitor=visitor, conversation=conversation, source=LeadSource.HUMAN_SUPPORT_REQUEST
    )

    title = f"Live agent requested: {visitor.name or 'Unknown visitor'}"
    if reason:
        title += f" ({reason})"
    await notify(
        db,
        type=NotificationType.LIVE_AGENT_REQUEST,
        title=title,
        agent_id=agent.id,
        resource_type="live_agent_request",
        resource_id=request.id,
        link=f"/conversations/{conversation.id}",
    )

    recipient = agent.notification_email
    if not recipient:
        settings_row = await email_service.get_settings_row(db)
        recipient = settings_row.support_email if settings_row else None
    if recipient:
        try:
            await email_service.send_email(
                db,
                to_email=recipient,
                subject="New Live Agent Request",
                body_text=(
                    f"Name: {visitor.name or 'N/A'}\n"
                    f"Email: {visitor.email or 'N/A'}\n"
                    f"Phone: {visitor.phone or 'N/A'}\n"
                    f"Reason: {reason or 'N/A'}\n"
                    f"Agent: {agent.name}\n"
                    f"Requested: {request.requested_at.isoformat()}\n"
                    f"Conversation: {conversation.id}\n"
                ),
            )
        except Exception:
            logger.exception("Failed to send handoff notification email for request %s", request.id)
            await notify(
                db,
                type=NotificationType.EMAIL_FAILED,
                title="Failed to send live agent request email",
                agent_id=agent.id,
                resource_type="live_agent_request",
                resource_id=request.id,
            )

    return request


async def assign_operator(db: AsyncSession, request: LiveAgentRequest, operator_id: uuid.UUID) -> LiveAgentRequest:
    request.assigned_operator_id = operator_id
    request.status = LiveAgentRequestStatus.ASSIGNED
    request.assigned_at = datetime.now(timezone.utc)
    await db.flush()
    return request


async def activate(db: AsyncSession, request: LiveAgentRequest, conversation: Conversation) -> LiveAgentRequest:
    request.status = LiveAgentRequestStatus.ACTIVE
    conversation.status = ConversationStatus.HUMAN_ACTIVE
    await db.flush()
    return request


async def resolve(db: AsyncSession, request: LiveAgentRequest, conversation: Conversation) -> LiveAgentRequest:
    request.status = LiveAgentRequestStatus.RESOLVED
    request.resolved_at = datetime.now(timezone.utc)
    conversation.status = ConversationStatus.RESOLVED
    conversation.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return request
