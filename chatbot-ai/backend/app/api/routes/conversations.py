import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.agent import OperatorAssignment
from app.models.conversation import Conversation, Message, Visitor
from app.models.enums import ConversationStatus, MessageSender, UserRole
from app.models.user import User
from app.schemas.conversation import (
    ConversationDetail,
    ConversationListItem,
    MessageOut,
    PaginatedConversations,
    SendOperatorMessageRequest,
)
from app.services.audit_service import log_action
from app.services.handoff_service import activate, assign_operator, get_active_request

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_list_item(conv: Conversation, visitor: Visitor) -> ConversationListItem:
    return ConversationListItem(
        id=conv.id,
        agent_id=conv.agent_id,
        visitor_name=visitor.name,
        visitor_email=visitor.email,
        visitor_phone=visitor.phone,
        status=conv.status,
        assigned_operator_id=conv.assigned_operator_id,
        started_at=conv.started_at,
        last_message_at=conv.last_message_at,
    )


@router.get("", response_model=PaginatedConversations)
async def list_conversations(
    agent_id: uuid.UUID | None = None,
    status_filter: ConversationStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedConversations:
    query = select(Conversation, Visitor).join(Visitor, Conversation.visitor_id == Visitor.id)
    count_query = select(func.count()).select_from(Conversation)

    role = UserRole(user.role.name)
    if role == UserRole.SUPPORT_AGENT:
        assigned_subq = select(OperatorAssignment.agent_id).where(OperatorAssignment.user_id == user.id)
        query = query.where(Conversation.agent_id.in_(assigned_subq))
        count_query = count_query.where(Conversation.agent_id.in_(assigned_subq))

    if agent_id:
        query = query.where(Conversation.agent_id == agent_id)
        count_query = count_query.where(Conversation.agent_id == agent_id)
    if status_filter:
        query = query.where(Conversation.status == status_filter)
        count_query = count_query.where(Conversation.status == status_filter)

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(Conversation.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).all()

    return PaginatedConversations(
        items=[_to_list_item(conv, visitor) for conv, visitor in rows], total=total, page=page, page_size=page_size
    )


async def _get_conversation_with_access(db: AsyncSession, conversation_id: uuid.UUID, user: User) -> Conversation:
    result = await db.execute(
        select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")

    role = UserRole(user.role.name)
    if role == UserRole.SUPPORT_AGENT:
        assignment = await db.execute(
            select(OperatorAssignment).where(
                OperatorAssignment.user_id == user.id, OperatorAssignment.agent_id == conversation.agent_id
            )
        )
        if assignment.scalar_one_or_none() is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not assigned to this agent")

    return conversation


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ConversationDetail:
    conversation = await _get_conversation_with_access(db, conversation_id, user)
    visitor = (await db.execute(select(Visitor).where(Visitor.id == conversation.visitor_id))).scalar_one()

    item = _to_list_item(conversation, visitor)
    return ConversationDetail(**item.model_dump(), messages=[MessageOut.model_validate(m) for m in conversation.messages])


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_operator_message(
    conversation_id: uuid.UUID,
    body: SendOperatorMessageRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    conversation = await _get_conversation_with_access(db, conversation_id, user)
    if conversation.status not in (ConversationStatus.HUMAN_ACTIVE, ConversationStatus.WAITING_FOR_AGENT):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Conversation is not active for a human agent")

    message = Message(
        conversation_id=conversation.id, sender_type=MessageSender.OPERATOR, sender_user_id=user.id, content=body.content
    )
    db.add(message)
    conversation.last_message_at = datetime.now(timezone.utc)
    if conversation.status == ConversationStatus.WAITING_FOR_AGENT:
        conversation.status = ConversationStatus.HUMAN_ACTIVE
        conversation.assigned_operator_id = user.id
    await db.flush()
    await log_action(
        db, user_id=user.id, action="conversation_operator_message", resource_type="conversation",
        resource_id=conversation.id, ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return MessageOut.model_validate(message)


@router.post("/{conversation_id}/resolve", response_model=ConversationListItem)
async def resolve_conversation(
    conversation_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ConversationListItem:
    conversation = await _get_conversation_with_access(db, conversation_id, user)
    conversation.status = ConversationStatus.RESOLVED
    conversation.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, user_id=user.id, action="conversation_resolved", resource_type="conversation",
        resource_id=conversation.id, ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    visitor = (await db.execute(select(Visitor).where(Visitor.id == conversation.visitor_id))).scalar_one()
    return _to_list_item(conversation, visitor)


@router.post("/{conversation_id}/close", response_model=ConversationListItem)
async def close_conversation(
    conversation_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ConversationListItem:
    conversation = await _get_conversation_with_access(db, conversation_id, user)
    conversation.status = ConversationStatus.CLOSED
    await db.flush()
    await log_action(
        db, user_id=user.id, action="conversation_closed", resource_type="conversation",
        resource_id=conversation.id, ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    visitor = (await db.execute(select(Visitor).where(Visitor.id == conversation.visitor_id))).scalar_one()
    return _to_list_item(conversation, visitor)


@router.post("/{conversation_id}/assign", response_model=ConversationListItem)
async def assign_conversation(
    conversation_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ConversationListItem:
    """An operator accepts a waiting conversation, taking it over from the
    AI and from the live-agent-request queue."""

    conversation = await _get_conversation_with_access(db, conversation_id, user)
    if conversation.status != ConversationStatus.WAITING_FOR_AGENT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Conversation is not waiting for an agent")

    conversation.status = ConversationStatus.HUMAN_ACTIVE
    conversation.assigned_operator_id = user.id
    await db.flush()

    live_request = await get_active_request(db, conversation.id)
    if live_request is not None:
        await assign_operator(db, live_request, user.id)
        await activate(db, live_request, conversation)

    await log_action(
        db, user_id=user.id, action="conversation_assigned", resource_type="conversation",
        resource_id=conversation.id, ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    visitor = (await db.execute(select(Visitor).where(Visitor.id == conversation.visitor_id))).scalar_one()
    return _to_list_item(conversation, visitor)
