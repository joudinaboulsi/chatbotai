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
from app.models.enums import AgentChannel, AgentStatus, ConversationStatus, LeadStatus, MessageSender, UserRole
from app.models.lead import Lead
from app.models.user import User
from app.schemas.conversation import ConversationDetail, MessageOut
from app.schemas.lead import LeadOut, LeadUpdate, PaginatedLeads
from app.services.audit_service import log_action

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=PaginatedLeads)
async def list_leads(
    agent_id: uuid.UUID | None = None,
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedLeads:
    query = select(Lead)
    count_query = select(func.count()).select_from(Lead)
    status_count_query = select(Lead.status, func.count()).select_from(Lead).group_by(Lead.status)

    role = UserRole(user.role.name)
    if role == UserRole.SUPPORT_AGENT:
        assigned_subq = select(OperatorAssignment.agent_id).where(OperatorAssignment.user_id == user.id)
        query = query.where(Lead.agent_id.in_(assigned_subq))
        count_query = count_query.where(Lead.agent_id.in_(assigned_subq))
        status_count_query = status_count_query.where(Lead.agent_id.in_(assigned_subq))

    if agent_id:
        query = query.where(Lead.agent_id == agent_id)
        count_query = count_query.where(Lead.agent_id == agent_id)
        status_count_query = status_count_query.where(Lead.agent_id == agent_id)
    if status_filter:
        query = query.where(Lead.status == status_filter)
        count_query = count_query.where(Lead.status == status_filter)

    archived_clause = Lead.archived_at.is_not(None) if archived else Lead.archived_at.is_(None)
    query = query.where(archived_clause)
    count_query = count_query.where(archived_clause)
    status_count_query = status_count_query.where(archived_clause)

    total = (await db.execute(count_query)).scalar_one()
    status_count_rows = (await db.execute(status_count_query)).all()
    status_counts = {s.value: 0 for s in LeadStatus}
    for status_value, count_value in status_count_rows:
        status_counts[status_value.value] = count_value

    query = query.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    leads = (await db.execute(query)).scalars().all()
    return PaginatedLeads(
        items=[LeadOut.model_validate(l) for l in leads], total=total, page=page, page_size=page_size,
        status_counts=status_counts,
    )


async def _get_lead_with_access(db: AsyncSession, lead_id: uuid.UUID, user: User) -> Lead:
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

    role = UserRole(user.role.name)
    if role == UserRole.SUPPORT_AGENT:
        assignment = await db.execute(
            select(OperatorAssignment).where(
                OperatorAssignment.user_id == user.id, OperatorAssignment.agent_id == lead.agent_id
            )
        )
        if assignment.scalar_one_or_none() is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not assigned to this agent")
    return lead


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> LeadOut:
    lead = await _get_lead_with_access(db, lead_id, user)
    return LeadOut.model_validate(lead)


@router.put("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: uuid.UUID,
    body: LeadUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeadOut:
    lead = await _get_lead_with_access(db, lead_id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    await db.flush()
    await log_action(
        db, user_id=user.id, action="lead_updated", resource_type="lead", resource_id=lead.id,
        ip_address=request.client.host if request.client else None, details=body.model_dump(exclude_unset=True),
    )
    await db.commit()
    return LeadOut.model_validate(lead)


@router.post("/{lead_id}/archive", response_model=LeadOut)
async def archive_lead(
    lead_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LeadOut:
    lead = await _get_lead_with_access(db, lead_id, user)
    lead.archived_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, user_id=user.id, action="lead_archived", resource_type="lead", resource_id=lead.id,
        ip_address=request.client.host if request.client else None, details=None,
    )
    await db.commit()
    return LeadOut.model_validate(lead)


@router.post("/{lead_id}/unarchive", response_model=LeadOut)
async def unarchive_lead(
    lead_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LeadOut:
    lead = await _get_lead_with_access(db, lead_id, user)
    lead.archived_at = None
    await db.flush()
    await log_action(
        db, user_id=user.id, action="lead_unarchived", resource_type="lead", resource_id=lead.id,
        ip_address=request.client.host if request.client else None, details=None,
    )
    await db.commit()
    return LeadOut.model_validate(lead)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    lead = await _get_lead_with_access(db, lead_id, user)
    await log_action(
        db, user_id=user.id, action="lead_deleted", resource_type="lead", resource_id=lead.id,
        ip_address=request.client.host if request.client else None, details=None,
    )
    await db.delete(lead)
    await db.commit()


@router.post("/{lead_id}/whatsapp/start", response_model=ConversationDetail)
async def start_whatsapp_conversation(
    lead_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ConversationDetail:
    """Powers the Leads table's WhatsApp AI preview button. Creates (or
    reuses) a real Conversation under a dedicated channel=whatsapp Agent,
    seeded with this lead's already-known contact info, so it shows up
    everywhere a normal conversation would (dashboard stats, Conversations
    list) — it's a real record, just not yet wired to the actual WhatsApp
    Business API. Subsequent turns go through POST
    /conversations/{id}/whatsapp-reply, which reuses the exact same sales
    AI pipeline a real widget visitor's message would hit."""

    lead = await _get_lead_with_access(db, lead_id, user)

    agent_row = await db.execute(
        select(Agent).where(Agent.channel == AgentChannel.WHATSAPP, Agent.status == AgentStatus.ACTIVE).limit(1)
    )
    agent = agent_row.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No active WhatsApp agent configured yet — create one on the Agents page first.",
        )

    existing_visitor = None
    if lead.phone:
        visitor_row = await db.execute(
            select(Visitor).where(Visitor.agent_id == agent.id, Visitor.phone == lead.phone)
        )
        existing_visitor = visitor_row.scalar_one_or_none()

    if existing_visitor is not None:
        conv_row = await db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.visitor_id == existing_visitor.id)
            .order_by(Conversation.started_at.desc())
        )
        conversation = conv_row.scalars().first()
        if conversation is not None:
            return ConversationDetail(
                id=conversation.id, agent_id=conversation.agent_id,
                visitor_name=existing_visitor.name, visitor_email=existing_visitor.email,
                visitor_phone=existing_visitor.phone, status=conversation.status,
                assigned_operator_id=conversation.assigned_operator_id, started_at=conversation.started_at,
                last_message_at=conversation.last_message_at,
                message_count=len(conversation.messages),
                last_message_preview=None, archived_at=conversation.archived_at,
                messages=[MessageOut.model_validate(m) for m in conversation.messages],
            )

    visitor = Visitor(
        agent_id=agent.id, session_token=str(uuid.uuid4()),
        name=lead.name, email=lead.email, phone=lead.phone,
    )
    db.add(visitor)
    await db.flush()

    conversation = Conversation(agent_id=agent.id, visitor_id=visitor.id, status=ConversationStatus.AI_ACTIVE)
    db.add(conversation)
    await db.flush()

    greeting_name = lead.name or "there"
    opener = f"Hi {greeting_name}! 👋 This is {agent.company_name}"
    if lead.company:
        opener += f" — following up on your interest for {lead.company}"
    else:
        opener += " — following up on your interest in SMS solutions"
    opener += ". How can I help you today?"

    greeting = Message(conversation_id=conversation.id, sender_type=MessageSender.AI, content=opener)
    db.add(greeting)
    conversation.last_message_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, user_id=user.id, action="whatsapp_conversation_started", resource_type="lead",
        resource_id=lead.id, ip_address=None, details={"conversation_id": str(conversation.id)},
    )
    await db.commit()

    return ConversationDetail(
        id=conversation.id, agent_id=conversation.agent_id,
        visitor_name=visitor.name, visitor_email=visitor.email, visitor_phone=visitor.phone,
        status=conversation.status, assigned_operator_id=conversation.assigned_operator_id,
        started_at=conversation.started_at, last_message_at=conversation.last_message_at,
        message_count=1, last_message_preview=opener[:120], archived_at=None,
        messages=[MessageOut.model_validate(greeting)],
    )
