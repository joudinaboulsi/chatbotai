import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_agent_access, require_roles
from app.core.config import settings
from app.core.db import get_db
from app.models.enums import AgentStatus, UserRole
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentListItem, AgentOut, AgentUpdate, PaginatedAgents
from app.services import agent_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/agents", tags=["agents"])

_manage_roles = require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=PaginatedAgents)
async def list_agents(
    search: str | None = Query(default=None, max_length=255),
    status_filter: AgentStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAgents:
    agents, total = await agent_service.list_agents(
        db, user=user, search=search, status_filter=status_filter, page=page, page_size=page_size
    )
    return PaginatedAgents(
        items=[AgentListItem.model_validate(a) for a in agents], total=total, page=page, page_size=page_size
    )


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> AgentOut:
    agent = await agent_service.create_agent(db, body, created_by=user.id)
    await log_action(
        db,
        user_id=user.id,
        action="agent_created",
        resource_type="agent",
        resource_id=agent.id,
        ip_address=_client_ip(request),
        details={"name": agent.name},
    )
    await db.commit()
    return AgentOut.model_validate(agent)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    user: User = Depends(require_agent_access),
    db: AsyncSession = Depends(get_db),
) -> AgentOut:
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return AgentOut.model_validate(agent)


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> AgentOut:
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    agent = await agent_service.update_agent(db, agent, body)
    await log_action(
        db,
        user_id=user.id,
        action="agent_updated",
        resource_type="agent",
        resource_id=agent.id,
        ip_address=_client_ip(request),
        details=body.model_dump(exclude_unset=True),
    )
    await db.commit()
    return AgentOut.model_validate(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    await log_action(
        db,
        user_id=user.id,
        action="agent_deleted",
        resource_type="agent",
        resource_id=agent.id,
        ip_address=_client_ip(request),
        details={"name": agent.name},
    )
    await agent_service.delete_agent(db, agent)
    await db.commit()


@router.post("/{agent_id}/duplicate", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def duplicate_agent(
    agent_id: uuid.UUID,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> AgentOut:
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    new_agent = await agent_service.duplicate_agent(db, agent, created_by=user.id)
    await log_action(
        db,
        user_id=user.id,
        action="agent_duplicated",
        resource_type="agent",
        resource_id=new_agent.id,
        ip_address=_client_ip(request),
        details={"source_agent_id": str(agent.id)},
    )
    await db.commit()
    return AgentOut.model_validate(new_agent)


@router.post("/{agent_id}/activate", response_model=AgentOut)
async def activate_agent(
    agent_id: uuid.UUID,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> AgentOut:
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    agent = await agent_service.set_status(db, agent, AgentStatus.ACTIVE)
    await log_action(
        db, user_id=user.id, action="agent_activated", resource_type="agent", resource_id=agent.id,
        ip_address=_client_ip(request),
    )
    await db.commit()
    return AgentOut.model_validate(agent)


@router.post("/{agent_id}/deactivate", response_model=AgentOut)
async def deactivate_agent(
    agent_id: uuid.UUID,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> AgentOut:
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    agent = await agent_service.set_status(db, agent, AgentStatus.INACTIVE)
    await log_action(
        db, user_id=user.id, action="agent_deactivated", resource_type="agent", resource_id=agent.id,
        ip_address=_client_ip(request),
    )
    await db.commit()
    return AgentOut.model_validate(agent)


@router.get("/{agent_id}/embed-code")
async def get_embed_code(
    agent_id: uuid.UUID,
    user: User = Depends(require_agent_access),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    snippet = (
        f'<script src="{settings.WIDGET_SCRIPT_BASE_URL}/widget.js" '
        f'data-agent-id="{agent.id}"></script>'
    )
    return {"embed_code": snippet}
