import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.db import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.dashboard import DashboardCharts, DashboardStats
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_manage_roles = require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    agent_id: uuid.UUID | None = None, user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> DashboardStats:
    return await dashboard_service.get_stats(db, agent_id=agent_id)


@router.get("/charts", response_model=DashboardCharts)
async def get_charts(
    agent_id: uuid.UUID | None = None,
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> DashboardCharts:
    return await dashboard_service.get_charts(db, agent_id=agent_id, days=days)
