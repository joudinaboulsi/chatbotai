import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.schemas.auth import TokenPair, UserOut


class AuthError(Exception):
    """Raised for any login failure. The route layer maps this to a generic
    401 — callers must never learn whether the email or the password was
    the wrong part, to avoid user enumeration."""


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).options(selectinload(User.role)).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password")
    if user.status != UserStatus.ACTIVE:
        raise AuthError("Account is inactive")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return user


def issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.name),
        refresh_token=create_refresh_token(str(user.id)),
    )


class PasswordChangeError(Exception):
    """Raised when the supplied current_password doesn't match."""


async def update_profile(db: AsyncSession, user: User, *, name: str) -> User:
    user.name = name
    await db.flush()
    return user


async def change_password(db: AsyncSession, user: User, *, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise PasswordChangeError("Current password is incorrect")
    user.password_hash = hash_password(new_password)
    await db.flush()


def to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=UserRole(user.role.name),
        status=user.status,
    )
