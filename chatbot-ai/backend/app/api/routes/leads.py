import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.agent import OperatorAssignment
from app.models.enums import LeadStatus, UserRole
from app.models.lead import Lead
from app.models.user import User
from app.schemas.lead import LeadOut, LeadUpdate, PaginatedLeads
from app.services.audit_service import log_action

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=PaginatedLeads)
async def list_leads(
    agent_id: uuid.UUID | None = None,
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedLeads:
    query = select(Lead)
    count_query = select(func.count()).select_from(Lead)

    role = UserRole(user.role.name)
    if role == UserRole.SUPPORT_AGENT:
        assigned_subq = select(OperatorAssignment.agent_id).where(OperatorAssignment.user_id == user.id)
        query = query.where(Lead.agent_id.in_(assigned_subq))
        count_query = count_query.where(Lead.agent_id.in_(assigned_subq))

    if agent_id:
        query = query.where(Lead.agent_id == agent_id)
        count_query = count_query.where(Lead.agent_id == agent_id)
    if status_filter:
        query = query.where(Lead.status == status_filter)
        count_query = count_query.where(Lead.status == status_filter)

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    leads = (await db.execute(query)).scalars().all()
    return PaginatedLeads(
        items=[LeadOut.model_validate(l) for l in leads], total=total, page=page, page_size=page_size
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
