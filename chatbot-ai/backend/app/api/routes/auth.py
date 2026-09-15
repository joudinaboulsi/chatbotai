import uuid
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.rate_limit import limiter
from app.core.redis_client import get_redis
from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, ProfileUpdate, RefreshRequest, TokenPair, UserOut
from app.services import auth_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        user = await auth_service.authenticate(db, body.email, body.password)
    except auth_service.AuthError:
        await log_action(
            db,
            user_id=None,
            action="login_failed",
            resource_type="user",
            ip_address=request.client.host if request.client else None,
            details={"email": body.email},
        )
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    tokens = auth_service.issue_tokens(user)
    await log_action(
        db,
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")

    redis_client = get_redis()
    if await redis_client.get(f"revoked_refresh:{payload['jti']}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has been revoked")

    user = await auth_service.get_user_by_id(db, uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")

    new_access = create_access_token(str(user.id), user.role.name)
    return TokenPair(access_token=new_access, refresh_token=body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, user: User = Depends(get_current_user)) -> None:
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        return None

    ttl_seconds = payload.get("exp", 0) - int(datetime.now(timezone.utc).timestamp())
    if ttl_seconds > 0:
        redis_client = get_redis()
        await redis_client.set(f"revoked_refresh:{payload['jti']}", "1", ex=ttl_seconds)
    return None


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return auth_service.to_user_out(user)


@router.put("/me", response_model=UserOut)
async def update_me(
    body: ProfileUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> UserOut:
    user = await auth_service.update_profile(db, user, name=body.name)
    await db.commit()
    return auth_service.to_user_out(user)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    body: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await auth_service.change_password(
            db, user, current_password=body.current_password, new_password=body.new_password
        )
    except auth_service.PasswordChangeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")

    await log_action(
        db, user_id=user.id, action="password_changed", resource_type="user", resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
