"""Seed fixed roles and (optionally) the first Super Admin account.

Usage:
    python -m app.workers.seed

The admin password is never hardcoded: pass it via the ADMIN_PASSWORD env
var, or omit it and a random one is generated and printed once (it is not
recoverable afterwards — reset it via the admin panel if lost). Re-running
this script is safe: it only creates rows that don't already exist.
"""

import asyncio
import os
import secrets

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.role import Role
from app.models.user import User

FIXED_ROLES = [
    (UserRole.SUPER_ADMIN, "Full access to all agents, operators, and settings"),
    (UserRole.ADMIN, "Manage assigned agents, knowledge bases, and conversations"),
    (UserRole.SUPPORT_AGENT, "Handle live conversations for assigned agents"),
]


async def seed_roles(session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for role_enum, description in FIXED_ROLES:
        result = await session.execute(select(Role).where(Role.name == role_enum.value))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=role_enum.value, description=description)
            session.add(role)
            await session.flush()
        roles[role_enum.value] = role
    return roles


async def seed_admin(session, roles: dict[str, Role]) -> None:
    admin_email = os.environ.get("ADMIN_EMAIL")
    if not admin_email:
        print("ADMIN_EMAIL not set — skipping admin user creation.")
        return

    result = await session.execute(select(User).where(User.email == admin_email.lower()))
    if result.scalar_one_or_none() is not None:
        print(f"Admin user {admin_email} already exists — skipping.")
        return

    password = os.environ.get("ADMIN_PASSWORD")
    generated = password is None
    if generated:
        password = secrets.token_urlsafe(18)

    user = User(
        name=os.environ.get("ADMIN_NAME", "Administrator"),
        email=admin_email.lower(),
        password_hash=hash_password(password),
        role_id=roles[UserRole.SUPER_ADMIN.value].id,
    )
    session.add(user)
    await session.flush()

    print(f"Created Super Admin: {admin_email}")
    if generated:
        print(f"Generated password (shown once): {password}")
        print("Change this password immediately after first login.")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        roles = await seed_roles(session)
        await seed_admin(session, roles)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
