import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent, AgentBranding, OperatorAssignment
from app.models.enums import AgentStatus, UserRole
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentUpdate


async def create_agent(db: AsyncSession, data: AgentCreate, created_by: uuid.UUID) -> Agent:
    agent = Agent(
        name=data.name,
        company_name=data.company_name,
        industry=data.industry,
        description=data.description,
        remarks=data.remarks,
        languages=data.languages,
        notification_email=data.notification_email,
        channel=data.channel,
        created_by=created_by,
    )
    db.add(agent)
    await db.flush()

    # Every agent gets a branding row with sane defaults immediately, so
    # the widget/branding endpoints never have to special-case "not yet
    # configured" — there's always exactly one branding row per agent.
    db.add(AgentBranding(agent_id=agent.id))
    await db.flush()
    return agent


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    return result.scalar_one_or_none()


async def list_agents(
    db: AsyncSession,
    *,
    user: User,
    search: str | None,
    status_filter: AgentStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[Agent], int]:
    query = select(Agent)
    count_query = select(func.count()).select_from(Agent)

    role = UserRole(user.role.name)
    if role == UserRole.SUPPORT_AGENT:
        assigned_subq = select(OperatorAssignment.agent_id).where(OperatorAssignment.user_id == user.id)
        query = query.where(Agent.id.in_(assigned_subq))
        count_query = count_query.where(Agent.id.in_(assigned_subq))

    if search:
        pattern = f"%{search}%"
        query = query.where(Agent.name.ilike(pattern) | Agent.company_name.ilike(pattern))
        count_query = count_query.where(Agent.name.ilike(pattern) | Agent.company_name.ilike(pattern))

    if status_filter:
        query = query.where(Agent.status == status_filter)
        count_query = count_query.where(Agent.status == status_filter)

    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(Agent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    agents = (await db.execute(query)).scalars().all()
    return list(agents), total


async def update_agent(db: AsyncSession, agent: Agent, data: AgentUpdate) -> Agent:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await db.flush()
    return agent


async def set_status(db: AsyncSession, agent: Agent, status: AgentStatus) -> Agent:
    agent.status = status
    await db.flush()
    return agent


async def duplicate_agent(db: AsyncSession, agent: Agent, created_by: uuid.UUID) -> Agent:
    result = await db.execute(select(AgentBranding).where(AgentBranding.agent_id == agent.id))
    source_branding = result.scalar_one_or_none()

    new_agent = Agent(
        name=f"{agent.name} (Copy)",
        company_name=agent.company_name,
        industry=agent.industry,
        description=agent.description,
        remarks=agent.remarks,
        languages=list(agent.languages),
        notification_email=agent.notification_email,
        created_by=created_by,
    )
    db.add(new_agent)
    await db.flush()

    if source_branding:
        db.add(
            AgentBranding(
                agent_id=new_agent.id,
                primary_color=source_branding.primary_color,
                secondary_color=source_branding.secondary_color,
                background_color=source_branding.background_color,
                text_color=source_branding.text_color,
                button_color=source_branding.button_color,
                font_family=source_branding.font_family,
                font_size=source_branding.font_size,
                widget_position=source_branding.widget_position,
                widget_size=source_branding.widget_size,
                welcome_message=source_branding.welcome_message,
                placeholder_text=source_branding.placeholder_text,
                display_company_name=source_branding.display_company_name,
                display_agent_name=source_branding.display_agent_name,
                # Logo/avatar files are not duplicated — the new agent gets
                # its own upload rather than sharing a file reference whose
                # lifecycle (deletion, replacement) is tied to the original.
            )
        )
    else:
        db.add(AgentBranding(agent_id=new_agent.id))
    await db.flush()
    return new_agent


async def delete_agent(db: AsyncSession, agent: Agent) -> None:
    await db.delete(agent)
    await db.flush()


async def get_branding(db: AsyncSession, agent_id: uuid.UUID) -> AgentBranding | None:
    result = await db.execute(select(AgentBranding).where(AgentBranding.agent_id == agent_id))
    return result.scalar_one_or_none()
