import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.db import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.operator import OperatorCreate, OperatorOut, OperatorUpdate
from app.services import operator_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/operators", tags=["operators"])

_manage_roles = require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)


def _to_out(user: User) -> OperatorOut:
    return OperatorOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=UserRole(user.role.name),
        status=user.status,
        assigned_agent_ids=[a.agent_id for a in user.agent_assignments],
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def _guard_super_admin_escalation(actor: User, target_role: UserRole | None) -> None:
    if target_role == UserRole.SUPER_ADMIN and UserRole(actor.role.name) != UserRole.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a Super Admin can grant the Super Admin role")


@router.get("", response_model=list[OperatorOut])
async def list_operators(user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)) -> list[OperatorOut]:
    operators = await operator_service.list_operators(db)
    return [_to_out(o) for o in operators]


@router.post("", response_model=OperatorOut, status_code=status.HTTP_201_CREATED)
async def create_operator(
    body: OperatorCreate, request: Request, user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> OperatorOut:
    _guard_super_admin_escalation(user, body.role)
    try:
        operator = await operator_service.create_operator(
            db,
            name=body.name,
            email=body.email,
            password=body.password,
            role=body.role,
            assigned_agent_ids=body.assigned_agent_ids,
        )
        await log_action(
            db, user_id=user.id, action="operator_created", resource_type="user", resource_id=operator.id,
            ip_address=request.client.host if request.client else None, details={"email": operator.email},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    operator = await operator_service.get_operator(db, operator.id)
    return _to_out(operator)


@router.get("/{operator_id}", response_model=OperatorOut)
async def get_operator(
    operator_id: uuid.UUID, user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> OperatorOut:
    operator = await operator_service.get_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operator not found")
    return _to_out(operator)


@router.put("/{operator_id}", response_model=OperatorOut)
async def update_operator(
    operator_id: uuid.UUID,
    body: OperatorUpdate,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> OperatorOut:
    operator = await operator_service.get_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operator not found")
    _guard_super_admin_escalation(user, body.role)

    operator = await operator_service.update_operator(
        db,
        operator,
        name=body.name,
        role=body.role,
        status=body.status,
        assigned_agent_ids=body.assigned_agent_ids,
    )
    await log_action(
        db, user_id=user.id, action="operator_updated", resource_type="user", resource_id=operator.id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    operator = await operator_service.get_operator(db, operator_id)
    return _to_out(operator)


@router.delete("/{operator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_operator(
    operator_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    operator = await operator_service.get_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operator not found")
    if operator.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete your own account")
    await log_action(
        db, user_id=user.id, action="operator_deleted", resource_type="user", resource_id=operator.id,
        ip_address=request.client.host if request.client else None, details={"email": operator.email},
    )
    await operator_service.delete_operator(db, operator)
    await db.commit()
