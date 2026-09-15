import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.conversation import Conversation, Visitor
from app.models.enums import LeadSource, NotificationType
from app.models.lead import Lead
from app.services import email_service
from app.services.notification_service import notify

logger = logging.getLogger("app.leads")


async def get_lead_for_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> Lead | None:
    result = await db.execute(select(Lead).where(Lead.conversation_id == conversation_id))
    return result.scalar_one_or_none()


async def create_or_get_lead(
    db: AsyncSession,
    *,
    agent: Agent,
    visitor: Visitor,
    conversation: Conversation,
    source: LeadSource,
    notes: str | None = None,
) -> tuple[Lead, bool]:
    """Returns (lead, created). Idempotent per conversation for the lead
    row itself, but backfills name/email/phone onto an existing lead if
    they were still null and the visitor has since supplied them. A lead
    often gets created from an early keyword match (e.g. "quote") before
    the visitor has given any contact info — without this backfill it
    would sit with blank contact details forever even after the visitor
    later gives their name and email (e.g. via sales_ai_service's
    request_sales_contact tool)."""

    existing = await get_lead_for_conversation(db, conversation.id)
    if existing is not None:
        had_email = bool(existing.email)
        changed = False
        if existing.name is None and visitor.name is not None:
            existing.name = visitor.name
            changed = True
        if existing.email is None and visitor.email is not None:
            existing.email = visitor.email
            changed = True
        if existing.phone is None and visitor.phone is not None:
            existing.phone = visitor.phone
            changed = True
        if existing.notes is None and notes is not None:
            existing.notes = notes
            changed = True
        if not changed:
            return existing, False
        await db.flush()
        # A lead with no email is nearly unactionable for follow-up — if
        # staff were already notified about it blank, they're worth
        # notifying again now that there's an actual way to reach this
        # person. Repeat backfills (e.g. phone arriving later) don't
        # re-notify — email is the one field that flips "can't follow up"
        # into "can".
        if not had_email and existing.email:
            await _notify_new_lead(db, agent=agent, visitor=visitor, conversation=conversation, source=existing.source, lead=existing)
        return existing, False

    lead = Lead(
        agent_id=agent.id,
        visitor_id=visitor.id,
        conversation_id=conversation.id,
        name=visitor.name,
        email=visitor.email,
        phone=visitor.phone,
        source=source,
        notes=notes,
    )
    db.add(lead)
    await db.flush()

    await _notify_new_lead(db, agent=agent, visitor=visitor, conversation=conversation, source=source, lead=lead)

    return lead, True


async def _notify_new_lead(
    db: AsyncSession, *, agent: Agent, visitor: Visitor, conversation: Conversation, source: LeadSource, lead: Lead
) -> None:
    """Best-effort: wrapped in its own SAVEPOINT (not just try/except) so a
    failure here (DB enum drift, a transient issue, SMTP problems) can
    never abort the caller's transaction. create_or_get_lead now runs for
    every identified visitor, not just explicit buying-intent leads (see
    sales_ai_service's save_contact_info / VISITOR_IDENTIFIED source), so
    this is on the hot path of nearly every conversation — a plain
    try/except wouldn't be enough, since a failed flush leaves the whole
    Postgres transaction aborted and every later statement (including the
    route's final commit, which is what actually persists the visitor's
    message) would fail too."""
    try:
        async with db.begin_nested():
            await notify(
                db,
                type=NotificationType.NEW_LEAD,
                title=f"New lead: {visitor.name or 'Unknown visitor'}",
                body=f"Source: {source.value}",
                agent_id=agent.id,
                resource_type="lead",
                resource_id=lead.id,
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
                        subject=f"New {agent.company_name} Chatbot Lead",
                        body_text=(
                            f"Name: {visitor.name or 'N/A'}\n"
                            f"Email: {visitor.email or 'N/A'}\n"
                            f"Phone: {visitor.phone or 'N/A'}\n"
                            f"Agent: {agent.name}\n"
                            f"Source: {source.value}\n"
                            f"Conversation: {conversation.id}\n"
                        ),
                    )
                except Exception:
                    logger.exception("Failed to send lead notification email for lead %s", lead.id)
                    await notify(
                        db,
                        type=NotificationType.EMAIL_FAILED,
                        title="Failed to send lead notification email",
                        agent_id=agent.id,
                        resource_type="lead",
                        resource_id=lead.id,
                    )
    except Exception:
        logger.exception("Failed to notify about new lead %s", lead.id)
