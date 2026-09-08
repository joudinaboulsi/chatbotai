import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.agent import OperatorAssignment
from app.models.conversation import Conversation
from app.models.enums import LiveAgentRequestStatus, UserRole
from app.models.live_agent import LiveAgentRequest
from app.models.user import User
from app.schemas.live_agent import LiveAgentRequestOut
from app.services.audit_service import log_action
from app.services.handoff_service import activate, assign_operator, resolve

router = APIRouter(prefix="/live-agents", tags=["live-agents"])


@router.get("", response_model=list[LiveAgentRequestOut])
async def list_live_agent_requests(
    status_filter: LiveAgentRequestStatus | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LiveAgentRequestOut]:
    query = select(LiveAgentRequest)

    role = UserRole(user.role.name)
    if role == UserRole.SUPPORT_AGENT:
        assigned_subq = select(OperatorAssignment.agent_id).where(OperatorAssignment.user_id == user.id)
        query = query.where(LiveAgentRequest.agent_id.in_(assigned_subq))

    if status_filter:
        query = query.where(LiveAgentRequest.status == status_filter)

    query = query.order_by(LiveAgentRequest.requested_at.desc())
    requests = (await db.execute(query)).scalars().all()
    return [LiveAgentRequestOut.model_validate(r) for r in requests]


async def _get_request_with_access(db: AsyncSession, request_id: uuid.UUID, user: User) -> LiveAgentRequest:
    result = await db.execute(select(LiveAgentRequest).where(LiveAgentRequest.id == request_id))
    live_request = result.scalar_one_or_none()
    if live_request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Live agent request not found")

    role = UserRole(user.role.name)
    if role == UserRole.SUPPORT_AGENT:
        assignment = await db.execute(
            select(OperatorAssignment).where(
                OperatorAssignment.user_id == user.id, OperatorAssignment.agent_id == live_request.agent_id
            )
        )
        if assignment.scalar_one_or_none() is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not assigned to this agent")
    return live_request


@router.post("/{request_id}/assign", response_model=LiveAgentRequestOut)
async def assign_live_agent_request(
    request_id: uuid.UUID, http_request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LiveAgentRequestOut:
    live_request = await _get_request_with_access(db, request_id, user)
    conversation = (
        await db.execute(select(Conversation).where(Conversation.id == live_request.conversation_id))
    ).scalar_one()

    await assign_operator(db, live_request, user.id)
    await activate(db, live_request, conversation)
    conversation.assigned_operator_id = user.id
    await db.flush()

    await log_action(
        db, user_id=user.id, action="live_agent_request_assigned", resource_type="live_agent_request",
        resource_id=live_request.id, ip_address=http_request.client.host if http_request.client else None,
    )
    await db.commit()
    return LiveAgentRequestOut.model_validate(live_request)


@router.post("/{request_id}/resolve", response_model=LiveAgentRequestOut)
async def resolve_live_agent_request(
    request_id: uuid.UUID, http_request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LiveAgentRequestOut:
    live_request = await _get_request_with_access(db, request_id, user)
    conversation = (
        await db.execute(select(Conversation).where(Conversation.id == live_request.conversation_id))
    ).scalar_one()

    await resolve(db, live_request, conversation)
    await log_action(
        db, user_id=user.id, action="live_agent_request_resolved", resource_type="live_agent_request",
        resource_id=live_request.id, ip_address=http_request.client.host if http_request.client else None,
    )
    await db.commit()
    return LiveAgentRequestOut.model_validate(live_request)
