import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import OperatorAssignment
from app.models.enums import NotificationType, UserRole
from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User
from app.websocket.manager import manager


def _serialize(notification: Notification) -> dict:
    return {
        "id": str(notification.id),
        "type": notification.type.value,
        "title": notification.title,
        "body": notification.body,
        "resource_type": notification.resource_type,
        "resource_id": str(notification.resource_id) if notification.resource_id else None,
        "link": notification.link,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
    }


async def _recipient_user_ids(db: AsyncSession, agent_id: uuid.UUID | None) -> list[uuid.UUID | None]:
    """Every Super Admin/Admin gets notified always; Support Agents only if
    assigned to the relevant agent. Returns a list of user_ids to create one
    Notification row per recipient (None agent_id => admins/super-admins
    only, e.g. system-wide errors)."""

    result = await db.execute(
        select(User.id)
        .join(Role, User.role_id == Role.id)
        .where(Role.name.in_([UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value]))
    )
    recipients = list(result.scalars().all())

    if agent_id is not None:
        assigned = await db.execute(
            select(OperatorAssignment.user_id).where(OperatorAssignment.agent_id == agent_id)
        )
        recipients.extend(assigned.scalars().all())

    return list(set(recipients))


async def notify(
    db: AsyncSession,
    *,
    type: NotificationType,
    title: str,
    body: str | None = None,
    agent_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    link: str | None = None,
) -> list[Notification]:
    recipient_ids = await _recipient_user_ids(db, agent_id)
    notifications = []
    for user_id in recipient_ids:
        n = Notification(
            user_id=user_id,
            agent_id=agent_id,
            type=type,
            title=title,
            body=body,
            resource_type=resource_type,
            resource_id=resource_id,
            link=link,
        )
        db.add(n)
        notifications.append(n)
    await db.flush()

    for n in notifications:
        if n.user_id is not None:
            await manager.send_to_user(n.user_id, _serialize(n))

    return notifications
