from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Message
from app.models.enums import MessageSender

_ROLES = {
    MessageSender.VISITOR: "user",
    MessageSender.AI: "assistant",
    MessageSender.OPERATOR: "assistant",
}


async def recent(db: AsyncSession, conversation_id: UUID, limit: int = 12) -> list[tuple[str, str]]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = reversed(result.scalars().all())
    return [(_ROLES[m.sender_type], m.content) for m in messages if m.sender_type in _ROLES]
