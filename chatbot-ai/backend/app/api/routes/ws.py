import uuid

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import AsyncSessionLocal
from app.core.security import decode_token
from app.models.enums import UserStatus
from app.models.user import User
from app.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket, token: str) -> None:
    """Browsers can't attach an Authorization header to a WebSocket
    handshake, so the access token travels as a query parameter instead —
    hence this being its own endpoint rather than reusing get_current_user."""

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise jwt.PyJWTError("wrong token type")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        await websocket.close(code=4401)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).options(selectinload(User.role)).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or user.status != UserStatus.ACTIVE:
            await websocket.close(code=4401)
            return

    await manager.connect(user_id, websocket)
    try:
        while True:
            # Widget/admin client doesn't need to send anything — we just
            # need the receive loop to detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, websocket)
