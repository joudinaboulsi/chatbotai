import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.models.agent import OperatorAssignment
from app.models.enums import UserRole
from app.models.role import Role
from app.models.user import User


async def _role_by_name(db: AsyncSession, role: UserRole) -> Role:
    result = await db.execute(select(Role).where(Role.name == role.value))
    row = result.scalar_one_or_none()
    if row is None:
        row = Role(name=role.value, description=role.value)
        db.add(row)
        await db.flush()
    return row


async def list_operators(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).options(selectinload(User.role), selectinload(User.agent_assignments)).order_by(User.created_at.desc())
    )
    return list(result.scalars().all())


async def get_operator(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.agent_assignments))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def create_operator(
    db: AsyncSession, *, name: str, email: str, password: str, role: UserRole, assigned_agent_ids: list[uuid.UUID]
) -> User:
    role_row = await _role_by_name(db, role)
    user = User(name=name, email=email.lower(), password_hash=hash_password(password), role_id=role_row.id)
    db.add(user)
    await db.flush()

    for agent_id in assigned_agent_ids:
        db.add(OperatorAssignment(user_id=user.id, agent_id=agent_id))
    await db.flush()
    return user


async def update_operator(
    db: AsyncSession,
    user: User,
    *,
    name: str | None,
    role: UserRole | None,
    status,
    assigned_agent_ids: list[uuid.UUID] | None,
) -> User:
    if name is not None:
        user.name = name
    if role is not None:
        role_row = await _role_by_name(db, role)
        user.role_id = role_row.id
    if status is not None:
        user.status = status
    if assigned_agent_ids is not None:
        result = await db.execute(select(OperatorAssignment).where(OperatorAssignment.user_id == user.id))
        for existing in result.scalars().all():
            await db.delete(existing)
        await db.flush()
        for agent_id in assigned_agent_ids:
            db.add(OperatorAssignment(user_id=user.id, agent_id=agent_id))
    await db.flush()
    return user


async def delete_operator(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.flush()
