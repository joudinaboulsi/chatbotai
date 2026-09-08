import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.models.enums import ConversationStatus, LiveAgentRequestStatus, MessageSender
from app.models.lead import Lead
from app.models.live_agent import LiveAgentRequest
from app.schemas.dashboard import DailyCount, DashboardCharts, DashboardStats, StatusCount


def _maybe_filter_agent(query, column, agent_id: uuid.UUID | None):
    return query.where(column == agent_id) if agent_id else query


async def get_stats(db: AsyncSession, agent_id: uuid.UUID | None = None) -> DashboardStats:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    total_conversations = (
        await db.execute(_maybe_filter_agent(select(func.count()).select_from(Conversation), Conversation.agent_id, agent_id))
    ).scalar_one()

    active_conversations = (
        await db.execute(
            _maybe_filter_agent(
                select(func.count()).select_from(Conversation).where(
                    Conversation.status.in_(
                        [ConversationStatus.AI_ACTIVE, ConversationStatus.WAITING_FOR_AGENT, ConversationStatus.HUMAN_ACTIVE]
                    )
                ),
                Conversation.agent_id,
                agent_id,
            )
        )
    ).scalar_one()

    resolved_conversations = (
        await db.execute(
            _maybe_filter_agent(
                select(func.count()).select_from(Conversation).where(Conversation.status == ConversationStatus.RESOLVED),
                Conversation.agent_id,
                agent_id,
            )
        )
    ).scalar_one()

    new_leads = (
        await db.execute(_maybe_filter_agent(select(func.count()).select_from(Lead), Lead.agent_id, agent_id))
    ).scalar_one()

    leads_today = (
        await db.execute(
            _maybe_filter_agent(
                select(func.count()).select_from(Lead).where(Lead.created_at >= today_start), Lead.agent_id, agent_id
            )
        )
    ).scalar_one()
    leads_this_week = (
        await db.execute(
            _maybe_filter_agent(
                select(func.count()).select_from(Lead).where(Lead.created_at >= week_start), Lead.agent_id, agent_id
            )
        )
    ).scalar_one()
    leads_this_month = (
        await db.execute(
            _maybe_filter_agent(
                select(func.count()).select_from(Lead).where(Lead.created_at >= month_start), Lead.agent_id, agent_id
            )
        )
    ).scalar_one()

    live_waiting = (
        await db.execute(
            _maybe_filter_agent(
                select(func.count()).select_from(LiveAgentRequest).where(
                    LiveAgentRequest.status == LiveAgentRequestStatus.WAITING
                ),
                LiveAgentRequest.agent_id,
                agent_id,
            )
        )
    ).scalar_one()

    avg_response = await _average_response_time_seconds(db, agent_id)

    return DashboardStats(
        total_conversations=total_conversations,
        active_conversations=active_conversations,
        new_leads=new_leads,
        leads_today=leads_today,
        leads_this_week=leads_this_week,
        leads_this_month=leads_this_month,
        live_agent_requests_waiting=live_waiting,
        resolved_conversations=resolved_conversations,
        average_response_time_seconds=avg_response,
    )


async def _average_response_time_seconds(db: AsyncSession, agent_id: uuid.UUID | None) -> float | None:
    next_created_at = func.lead(Message.created_at).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )
    next_sender = func.lead(Message.sender_type).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )

    subq = select(
        Message.sender_type.label("sender_type"),
        Message.created_at.label("created_at"),
        Message.conversation_id.label("conversation_id"),
        next_created_at.label("next_created_at"),
        next_sender.label("next_sender"),
    )
    if agent_id:
        subq = subq.join(Conversation, Conversation.id == Message.conversation_id).where(
            Conversation.agent_id == agent_id
        )
    subq = subq.subquery()

    diff_seconds = func.extract("epoch", subq.c.next_created_at - subq.c.created_at)
    result = await db.execute(
        select(func.avg(diff_seconds)).where(
            subq.c.sender_type == MessageSender.VISITOR,
            subq.c.next_sender.in_([MessageSender.AI, MessageSender.OPERATOR]),
        )
    )
    value = result.scalar_one_or_none()
    return float(value) if value is not None else None


async def get_charts(db: AsyncSession, agent_id: uuid.UUID | None = None, days: int = 30) -> DashboardCharts:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day_col_conv = func.date_trunc("day", Conversation.started_at)
    conv_query = (
        select(day_col_conv.label("day"), func.count().label("count"))
        .where(Conversation.started_at >= since)
        .group_by(day_col_conv)
        .order_by(day_col_conv)
    )
    conv_query = _maybe_filter_agent(conv_query, Conversation.agent_id, agent_id)
    conv_rows = (await db.execute(conv_query)).all()

    day_col_lead = func.date_trunc("day", Lead.created_at)
    lead_query = (
        select(day_col_lead.label("day"), func.count().label("count"))
        .where(Lead.created_at >= since)
        .group_by(day_col_lead)
        .order_by(day_col_lead)
    )
    lead_query = _maybe_filter_agent(lead_query, Lead.agent_id, agent_id)
    lead_rows = (await db.execute(lead_query)).all()

    ai_vs_human_query = (
        select(
            case(
                (Conversation.status == ConversationStatus.HUMAN_ACTIVE, "human"),
                (Conversation.assigned_operator_id.is_not(None), "human"),
                else_="ai",
            ).label("kind"),
            func.count().label("count"),
        )
        .group_by("kind")
    )
    ai_vs_human_query = _maybe_filter_agent(ai_vs_human_query, Conversation.agent_id, agent_id)
    ai_vs_human_rows = (await db.execute(ai_vs_human_query)).all()

    status_query = select(Conversation.status.label("status"), func.count().label("count")).group_by(Conversation.status)
    status_query = _maybe_filter_agent(status_query, Conversation.agent_id, agent_id)
    status_rows = (await db.execute(status_query)).all()

    return DashboardCharts(
        conversations_over_time=[DailyCount(day=row.day.date(), count=row.count) for row in conv_rows],
        leads_over_time=[DailyCount(day=row.day.date(), count=row.count) for row in lead_rows],
        ai_vs_human_conversations=[StatusCount(status=row.kind, count=row.count) for row in ai_vs_human_rows],
        conversation_status_breakdown=[StatusCount(status=row.status.value, count=row.count) for row in status_rows],
    )
