import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.agent import Agent, AgentBranding, OperatorAssignment
from app.models.conversation import Conversation, Message, Visitor
from app.models.enums import AgentChannel, ConversationStatus, MessageSender, UserRole
from app.models.lead import Lead
from app.models.user import User
from app.schemas.conversation import (
    ConversationDetail,
    ConversationListItem,
    MessageOut,
    PaginatedConversations,
    SendOperatorMessageRequest,
    WhatsAppReplyRequest,
)
from app.services import conversation_service
from app.services.audit_service import log_action
from app.services.handoff_service import activate, assign_operator, get_active_request

router = APIRouter(prefix="/conversations", tags=["conversations"])

_PREVIEW_MAX_LEN = 120


def _preview(content: str | None) -> str | None:
    if not content:
        return None
    cleaned = " ".join(content.split())
    if len(cleaned) <= _PREVIEW_MAX_LEN:
        return cleaned
    return cleaned[:_PREVIEW_MAX_LEN].rstrip() + "…"


def _to_list_item(conv: Conversation, visitor: Visitor, message_count: int, last_message_content: str | None) -> ConversationListItem:
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
        message_count=message_count,
        last_message_preview=_preview(last_message_content),
        archived_at=conv.archived_at,
    )


def _to_list_item_from_loaded(conv: Conversation, visitor: Visitor) -> ConversationListItem:
    """Same as _to_list_item, but for callers that already have
    conv.messages eagerly loaded (via _get_conversation_with_access's
    selectinload) — reuses that instead of an extra count/preview query.
    Message.created_at ascending order is the relationship's default."""
    messages = conv.messages
    last_content = messages[-1].content if messages else None
    return _to_list_item(conv, visitor, len(messages), last_content)


@router.get("", response_model=PaginatedConversations)
async def list_conversations(
    agent_id: uuid.UUID | None = None,
    status_filter: ConversationStatus | None = Query(default=None, alias="status"),
    has_lead: bool | None = Query(default=None),
    archived: bool = Query(default=False),
    sort: str = Query(default="newest", pattern="^(newest|oldest|most_messages)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedConversations:
    message_count_subq = (
        select(func.count(Message.id)).where(Message.conversation_id == Conversation.id).correlate(Conversation).scalar_subquery()
    )
    last_message_subq = (
        select(Message.content)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )
    lead_exists = select(Lead.id).where(Lead.conversation_id == Conversation.id).correlate(Conversation).exists()

    query = (
        select(Conversation, Visitor, message_count_subq.label("message_count"), last_message_subq.label("last_message"))
        .join(Visitor, Conversation.visitor_id == Visitor.id)
    )
    count_query = select(func.count()).select_from(Conversation)
    status_count_query = select(Conversation.status, func.count()).select_from(Conversation).group_by(Conversation.status)

    role = UserRole(user.role.name)
    if role == UserRole.SUPPORT_AGENT:
        assigned_subq = select(OperatorAssignment.agent_id).where(OperatorAssignment.user_id == user.id)
        query = query.where(Conversation.agent_id.in_(assigned_subq))
        count_query = count_query.where(Conversation.agent_id.in_(assigned_subq))
        status_count_query = status_count_query.where(Conversation.agent_id.in_(assigned_subq))

    if agent_id:
        query = query.where(Conversation.agent_id == agent_id)
        count_query = count_query.where(Conversation.agent_id == agent_id)
        status_count_query = status_count_query.where(Conversation.agent_id == agent_id)
    if status_filter:
        query = query.where(Conversation.status == status_filter)
        count_query = count_query.where(Conversation.status == status_filter)
    if has_lead is not None:
        query = query.where(lead_exists if has_lead else ~lead_exists)
        count_query = count_query.where(lead_exists if has_lead else ~lead_exists)

    archived_clause = Conversation.archived_at.is_not(None) if archived else Conversation.archived_at.is_(None)
    query = query.where(archived_clause)
    count_query = count_query.where(archived_clause)
    status_count_query = status_count_query.where(archived_clause)

    total = (await db.execute(count_query)).scalar_one()
    status_count_rows = (await db.execute(status_count_query)).all()
    status_counts = {s.value: 0 for s in ConversationStatus}
    for status_value, count_value in status_count_rows:
        status_counts[status_value.value] = count_value

    if sort == "oldest":
        query = query.order_by(Conversation.started_at.asc())
    elif sort == "most_messages":
        query = query.order_by(message_count_subq.desc())
    else:
        query = query.order_by(Conversation.started_at.desc())

    query = query.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).all()

    return PaginatedConversations(
        items=[_to_list_item(conv, visitor, msg_count, last_msg) for conv, visitor, msg_count, last_msg in rows],
        total=total,
        page=page,
        page_size=page_size,
        status_counts=status_counts,
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

    item = _to_list_item_from_loaded(conversation, visitor)
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
    return _to_list_item_from_loaded(conversation, visitor)


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
    return _to_list_item_from_loaded(conversation, visitor)


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
    return _to_list_item_from_loaded(conversation, visitor)


@router.post("/{conversation_id}/archive", response_model=ConversationListItem)
async def archive_conversation(
    conversation_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ConversationListItem:
    conversation = await _get_conversation_with_access(db, conversation_id, user)
    conversation.archived_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, user_id=user.id, action="conversation_archived", resource_type="conversation",
        resource_id=conversation.id, ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    visitor = (await db.execute(select(Visitor).where(Visitor.id == conversation.visitor_id))).scalar_one()
    return _to_list_item_from_loaded(conversation, visitor)


@router.post("/{conversation_id}/unarchive", response_model=ConversationListItem)
async def unarchive_conversation(
    conversation_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ConversationListItem:
    conversation = await _get_conversation_with_access(db, conversation_id, user)
    conversation.archived_at = None
    await db.flush()
    await log_action(
        db, user_id=user.id, action="conversation_unarchived", resource_type="conversation",
        resource_id=conversation.id, ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    visitor = (await db.execute(select(Visitor).where(Visitor.id == conversation.visitor_id))).scalar_one()
    return _to_list_item_from_loaded(conversation, visitor)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    conversation = await _get_conversation_with_access(db, conversation_id, user)
    await log_action(
        db, user_id=user.id, action="conversation_deleted", resource_type="conversation",
        resource_id=conversation.id, ip_address=request.client.host if request.client else None,
    )
    await db.delete(conversation)
    await db.commit()


@router.post("/{conversation_id}/whatsapp-reply", response_model=ConversationDetail)
async def whatsapp_reply(
    conversation_id: uuid.UUID,
    body: WhatsAppReplyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    """The WhatsApp preview modal's operator types this AS the lead — it's
    fed through the exact same handle_visitor_message pipeline a real
    widget visitor's message would hit, so the sales AI, its tools, and
    every guardrail behave identically. Only allowed on a conversation
    whose agent is channel=whatsapp, so this can't be used to spoof a
    real web visitor's turn."""

    conversation = await _get_conversation_with_access(db, conversation_id, user)

    agent_row = await db.execute(
        select(Agent, AgentBranding)
        .join(AgentBranding, AgentBranding.agent_id == Agent.id)
        .where(Agent.id == conversation.agent_id)
    )
    agent, branding = agent_row.first()
    if agent.channel != AgentChannel.WHATSAPP:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a WhatsApp conversation")

    visitor = (await db.execute(select(Visitor).where(Visitor.id == conversation.visitor_id))).scalar_one()

    await conversation_service.handle_visitor_message(
        db, agent=agent, branding=branding, conversation=conversation, visitor=visitor,
        text=body.text, quick_reply=None, locale="en",
    )
    await db.commit()

    # conversation.messages was already loaded (selectinload, in
    # _get_conversation_with_access) before handle_visitor_message added
    # the new visitor/AI rows — with expire_on_commit=False that in-memory
    # collection doesn't pick up the new rows on its own, so query Message
    # directly instead of trusting the relationship here.
    messages_result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    messages = messages_result.scalars().all()
    last_content = messages[-1].content if messages else None

    return ConversationDetail(
        id=conversation.id, agent_id=conversation.agent_id,
        visitor_name=visitor.name, visitor_email=visitor.email, visitor_phone=visitor.phone,
        status=conversation.status, assigned_operator_id=conversation.assigned_operator_id,
        started_at=conversation.started_at, last_message_at=conversation.last_message_at,
        message_count=len(messages), last_message_preview=_preview(last_content),
        archived_at=conversation.archived_at,
        messages=[MessageOut.model_validate(m) for m in messages],
    )
