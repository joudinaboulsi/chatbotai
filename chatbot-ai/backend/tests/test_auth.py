import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.enums import UserRole, UserStatus
from app.models.role import Role
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _create_user(
    db_session: AsyncSession,
    *,
    email: str,
    password: str,
    role_name: str = UserRole.SUPER_ADMIN.value,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    result = await db_session.execute(Role.__table__.select().where(Role.name == role_name))
    role_row = result.first()
    if role_row is None:
        role = Role(name=role_name, description=role_name)
        db_session.add(role)
        await db_session.flush()
        role_id = role.id
    else:
        role_id = role_row.id

    user = User(
        name="Test User",
        email=email,
        password_hash=hash_password(password),
        role_id=role_id,
        status=status,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


async def test_login_success(client: AsyncClient, db_session: AsyncSession):
    await _create_user(db_session, email="admin@example.com", password="CorrectHorse123!")

    resp = await client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "CorrectHorse123!"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, db_session: AsyncSession):
    await _create_user(db_session, email="admin2@example.com", password="CorrectHorse123!")

    resp = await client.post(
        "/api/auth/login", json={"email": "admin2@example.com", "password": "WrongPassword!"}
    )
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


async def test_login_unknown_email_same_error_as_wrong_password(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


async def test_login_inactive_user_rejected(client: AsyncClient, db_session: AsyncSession):
    await _create_user(
        db_session,
        email="inactive@example.com",
        password="CorrectHorse123!",
        status=UserStatus.INACTIVE,
    )

    resp = await client.post(
        "/api/auth/login", json={"email": "inactive@example.com", "password": "CorrectHorse123!"}
    )
    assert resp.status_code == 401


async def test_me_requires_authentication(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_with_valid_token(client: AsyncClient, db_session: AsyncSession):
    await _create_user(db_session, email="whoami@example.com", password="CorrectHorse123!")
    login = await client.post(
        "/api/auth/login", json={"email": "whoami@example.com", "password": "CorrectHorse123!"}
    )
    token = login.json()["access_token"]

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "whoami@example.com"
    assert body["role"] == "super_admin"


async def test_me_rejects_garbage_token(client: AsyncClient):
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


async def test_refresh_issues_new_access_token(client: AsyncClient, db_session: AsyncSession):
    await _create_user(db_session, email="refresher@example.com", password="CorrectHorse123!")
    login = await client.post(
        "/api/auth/login", json={"email": "refresher@example.com", "password": "CorrectHorse123!"}
    )
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_logout_revokes_refresh_token(client: AsyncClient, db_session: AsyncSession):
    await _create_user(db_session, email="logout@example.com", password="CorrectHorse123!")
    login = await client.post(
        "/api/auth/login", json={"email": "logout@example.com", "password": "CorrectHorse123!"}
    )
    tokens = login.json()

    logout_resp = await client.post(
        "/api/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert logout_resp.status_code == 204

    refresh_resp = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_resp.status_code == 401
    assert "revoked" in refresh_resp.json()["detail"].lower()


async def test_login_rate_limited_after_five_attempts(client: AsyncClient):
    for _ in range(5):
        resp = await client.post(
            "/api/auth/login", json={"email": "flood@example.com", "password": "wrong"}
        )
        assert resp.status_code == 401

    resp = await client.post("/api/auth/login", json={"email": "flood@example.com", "password": "wrong"})
    assert resp.status_code == 429
