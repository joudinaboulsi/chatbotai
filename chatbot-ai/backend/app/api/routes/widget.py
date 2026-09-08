"""Public, unauthenticated endpoints for the embeddable chat widget. This
router must never expose anything beyond what a visitor should see — no
admin fields, no other visitors' data, no internal IDs beyond the
conversation/visitor the caller's own session_token already grants them."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.rate_limit import limiter
from app.models.agent import Agent, AgentBranding
from app.models.conversation import Conversation, Message, Visitor
from app.models.enums import AgentStatus, ConversationStatus, LeadSource
from app.schemas.widget import (
    HandoffRequest,
    LeadRequest,
    MessageOut,
    MessagesSinceResponse,
    SendMessageRequest,
    SendMessageResponse,
    SessionRequest,
    SessionResponse,
    VisitorUpdateRequest,
    WidgetConfigOut,
)
from app.services import conversation_service, smsc_service
from app.services.lead_service import create_or_get_lead
from app.services.visitor_validation import validate_email_address, validate_name, validate_phone

router = APIRouter(prefix="/widget", tags=["widget"])

_widget_rate = f"{settings.RATE_LIMIT_WIDGET_PER_MINUTE}/minute"


async def _get_active_agent_and_branding(db: AsyncSession, agent_id: uuid.UUID) -> tuple[Agent, AgentBranding]:
    result = await db.execute(
        select(Agent, AgentBranding)
        .join(AgentBranding, AgentBranding.agent_id == Agent.id)
        .where(Agent.id == agent_id, Agent.status == AgentStatus.ACTIVE)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return row


async def _get_visitor_or_404(db: AsyncSession, agent_id: uuid.UUID, session_token: str) -> Visitor:
    result = await db.execute(
        select(Visitor).where(Visitor.agent_id == agent_id, Visitor.session_token == session_token)
    )
    visitor = result.scalar_one_or_none()
    if visitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return visitor


def _detect_locale(request: Request) -> str:
    """Arabic if the browser's Accept-Language says so, English otherwise.
    Every fetch() from the widget already sends this header automatically
    — no widget.js change needed for the backend side of this."""
    header = (request.headers.get("accept-language") or "").strip().lower()
    primary = header.split(",")[0].split(";")[0].split("-")[0].strip()
    return "ar" if primary == "ar" else "en"


@router.get("/config/{agent_id}", response_model=WidgetConfigOut)
async def get_widget_config(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> WidgetConfigOut:
    agent, branding = await _get_active_agent_and_branding(db, agent_id)
    return WidgetConfigOut(
        agent_id=agent.id,
        company_name=branding.display_company_name or agent.company_name,
        agent_name=branding.display_agent_name or agent.name,
        logo_url=branding.logo_url,
        avatar_url=branding.avatar_url,
        primary_color=branding.primary_color,
        secondary_color=branding.secondary_color,
        background_color=branding.background_color,
        text_color=branding.text_color,
        button_color=branding.button_color,
        font_family=branding.font_family,
        font_size=branding.font_size,
        widget_position=branding.widget_position,
        widget_size=branding.widget_size,
        welcome_message=branding.welcome_message,
        placeholder_text=branding.placeholder_text,
    )


@router.post("/{agent_id}/session", response_model=SessionResponse)
@limiter.limit(_widget_rate)
async def create_session(
    agent_id: uuid.UUID, request: Request, body: SessionRequest, db: AsyncSession = Depends(get_db)
) -> SessionResponse:
    agent, branding = await _get_active_agent_and_branding(db, agent_id)
    locale = _detect_locale(request)
    visitor, token = await conversation_service.get_or_create_visitor(
        db,
        agent_id=agent.id,
        session_token=body.session_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    conversation, is_new = await conversation_service.get_or_create_conversation(db, agent=agent, visitor=visitor)

    initial_messages: list[Message] = []
    if is_new:
        identified_name: str | None = None
        is_support_login = False
        if body.login_token:
            identified = await smsc_service.identify_from_widget_login_token(
                db, conversation_id=conversation.id, visitor_id=visitor.id, login_token=body.login_token
            )
            if identified:
                identified_name, role = identified
                if visitor.name is None:
                    visitor.name = identified_name
                is_support_login = role == "support"

        greeting = await conversation_service.build_greeting_message(
            db,
            conversation=conversation,
            locale=locale,
            name=identified_name,
            is_support=is_support_login,
        )
        initial_messages = [greeting]

    await db.commit()

    if not initial_messages:
        result = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at)
        )
        initial_messages = list(result.scalars().all())

    return SessionResponse(
        session_token=token,
        conversation_id=conversation.id,
        conversation_status=conversation.status,
        messages=[MessageOut.model_validate(m) for m in initial_messages],
    )


@router.post("/{agent_id}/message", response_model=SendMessageResponse)
@limiter.limit(_widget_rate)
async def send_message(
    agent_id: uuid.UUID, request: Request, body: SendMessageRequest, db: AsyncSession = Depends(get_db)
) -> SendMessageResponse:
    agent, branding = await _get_active_agent_and_branding(db, agent_id)
    visitor = await _get_visitor_or_404(db, agent_id, body.session_token)
    conversation, _ = await conversation_service.get_or_create_conversation(db, agent=agent, visitor=visitor)

    reply_messages = await conversation_service.handle_visitor_message(
        db,
        agent=agent,
        branding=branding,
        conversation=conversation,
        visitor=visitor,
        text=body.message,
        quick_reply=body.quick_reply,
        locale=_detect_locale(request),
    )
    await db.commit()

    return SendMessageResponse(
        conversation_status=conversation.status,
        messages=[MessageOut.model_validate(m) for m in reply_messages],
    )


@router.get("/{agent_id}/messages", response_model=MessagesSinceResponse)
@limiter.limit(_widget_rate)
async def get_messages_since(
    agent_id: uuid.UUID,
    request: Request,
    session_token: str,
    after: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> MessagesSinceResponse:
    await _get_active_agent_and_branding(db, agent_id)
    visitor = await _get_visitor_or_404(db, agent_id, session_token)

    open_statuses = (ConversationStatus.AI_ACTIVE, ConversationStatus.WAITING_FOR_AGENT, ConversationStatus.HUMAN_ACTIVE)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.visitor_id == visitor.id, Conversation.status.in_(open_statuses))
        .order_by(Conversation.started_at.desc())
    )
    conversation = result.scalars().first()
    if conversation is None:
        return MessagesSinceResponse(conversation_status=ConversationStatus.CLOSED, messages=[])

    query = select(Message).where(Message.conversation_id == conversation.id)
    if after:
        try:
            after_message = await db.get(Message, uuid.UUID(after))
        except ValueError:
            after_message = None
        if after_message is not None:
            query = query.where(Message.created_at > after_message.created_at)
    query = query.order_by(Message.created_at)

    messages = (await db.execute(query)).scalars().all()
    return MessagesSinceResponse(
        conversation_status=conversation.status, messages=[MessageOut.model_validate(m) for m in messages]
    )


@router.post("/{agent_id}/visitor", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(_widget_rate)
async def update_visitor(
    agent_id: uuid.UUID, request: Request, body: VisitorUpdateRequest, db: AsyncSession = Depends(get_db)
) -> None:
    await _get_active_agent_and_branding(db, agent_id)
    visitor = await _get_visitor_or_404(db, agent_id, body.session_token)

    if body.name is not None:
        name = validate_name(body.name)
        if name is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid name")
        visitor.name = name
    if body.email is not None:
        email = validate_email_address(body.email)
        if email is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid email address")
        visitor.email = email
    if body.phone is not None:
        phone = validate_phone(body.phone)
        if phone is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid phone number")
        visitor.phone = phone

    await db.commit()


@router.post("/{agent_id}/lead", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(_widget_rate)
async def create_lead(
    agent_id: uuid.UUID, request: Request, body: LeadRequest, db: AsyncSession = Depends(get_db)
) -> None:
    agent, _ = await _get_active_agent_and_branding(db, agent_id)
    visitor = await _get_visitor_or_404(db, agent_id, body.session_token)
    conversation, _ = await conversation_service.get_or_create_conversation(db, agent=agent, visitor=visitor)
    try:
        source = LeadSource(body.source) if body.source else LeadSource.MANUAL
    except ValueError:
        source = LeadSource.MANUAL
    await create_or_get_lead(db, agent=agent, visitor=visitor, conversation=conversation, source=source)
    await db.commit()


@router.post("/{agent_id}/handoff", response_model=SendMessageResponse)
@limiter.limit(_widget_rate)
async def handoff(
    agent_id: uuid.UUID, request: Request, body: HandoffRequest, db: AsyncSession = Depends(get_db)
) -> SendMessageResponse:
    agent, _ = await _get_active_agent_and_branding(db, agent_id)
    visitor = await _get_visitor_or_404(db, agent_id, body.session_token)
    conversation, _ = await conversation_service.get_or_create_conversation(db, agent=agent, visitor=visitor)
    reply = await conversation_service.handle_handoff_choice(
        db,
        agent=agent,
        conversation=conversation,
        visitor=visitor,
        accepted=body.accepted,
        locale=_detect_locale(request),
    )
    await db.commit()
    return SendMessageResponse(conversation_status=conversation.status, messages=[MessageOut.model_validate(reply)])
