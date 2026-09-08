import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import OperatorAssignment
from app.models.enums import UserRole
from tests.test_auth import _create_user

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str = "CorrectHorse123!") -> dict[str, str]:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_admin(db_session: AsyncSession, email: str) -> None:
    await _create_user(db_session, email=email, password="CorrectHorse123!", role_name=UserRole.ADMIN.value)


async def test_create_agent_requires_admin_role(client: AsyncClient, db_session: AsyncSession):
    await _create_user(
        db_session, email="support1@example.com", password="CorrectHorse123!", role_name=UserRole.SUPPORT_AGENT.value
    )
    headers = await _login(client, "support1@example.com")

    resp = await client.post(
        "/api/agents", json={"name": "Tawasol Agent", "company_name": "Tawasol"}, headers=headers
    )
    assert resp.status_code == 403


async def test_create_and_get_agent(client: AsyncClient, db_session: AsyncSession):
    await _make_admin(db_session, "admin1@example.com")
    headers = await _login(client, "admin1@example.com")

    resp = await client.post(
        "/api/agents",
        json={
            "name": "Tawasol Agent",
            "company_name": "Tawasol",
            "industry": "Telecommunications",
            "languages": ["en", "ar"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    agent = resp.json()
    assert agent["name"] == "Tawasol Agent"
    assert agent["status"] == "active"

    get_resp = await client.get(f"/api/agents/{agent['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["company_name"] == "Tawasol"

    # Branding row is created automatically with defaults.
    branding_resp = await client.get(f"/api/agents/{agent['id']}/branding", headers=headers)
    assert branding_resp.status_code == 200
    assert branding_resp.json()["primary_color"] == "#0066A1"


async def test_update_activate_deactivate_agent(client: AsyncClient, db_session: AsyncSession):
    await _make_admin(db_session, "admin2@example.com")
    headers = await _login(client, "admin2@example.com")

    create_resp = await client.post(
        "/api/agents", json={"name": "Agent A", "company_name": "Acme"}, headers=headers
    )
    agent_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/agents/{agent_id}", json={"description": "Updated description"}, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "Updated description"

    deactivate_resp = await client.post(f"/api/agents/{agent_id}/deactivate", headers=headers)
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["status"] == "inactive"

    activate_resp = await client.post(f"/api/agents/{agent_id}/activate", headers=headers)
    assert activate_resp.status_code == 200
    assert activate_resp.json()["status"] == "active"


async def test_duplicate_agent_copies_branding_not_id(client: AsyncClient, db_session: AsyncSession):
    await _make_admin(db_session, "admin3@example.com")
    headers = await _login(client, "admin3@example.com")

    create_resp = await client.post(
        "/api/agents", json={"name": "Original", "company_name": "Acme"}, headers=headers
    )
    agent_id = create_resp.json()["id"]
    await client.put(
        f"/api/agents/{agent_id}/branding", json={"primary_color": "#FF00AA"}, headers=headers
    )

    dup_resp = await client.post(f"/api/agents/{agent_id}/duplicate", headers=headers)
    assert dup_resp.status_code == 201
    dup = dup_resp.json()
    assert dup["id"] != agent_id
    assert dup["name"] == "Original (Copy)"

    dup_branding = await client.get(f"/api/agents/{dup['id']}/branding", headers=headers)
    assert dup_branding.json()["primary_color"] == "#FF00AA"


async def test_delete_agent_requires_super_admin(client: AsyncClient, db_session: AsyncSession):
    await _make_admin(db_session, "admin4@example.com")
    headers = await _login(client, "admin4@example.com")

    create_resp = await client.post(
        "/api/agents", json={"name": "ToDelete", "company_name": "Acme"}, headers=headers
    )
    agent_id = create_resp.json()["id"]

    # Admin (not Super Admin) may not delete.
    forbidden_resp = await client.delete(f"/api/agents/{agent_id}", headers=headers)
    assert forbidden_resp.status_code == 403

    await _create_user(
        db_session, email="root@example.com", password="CorrectHorse123!", role_name=UserRole.SUPER_ADMIN.value
    )
    super_headers = await _login(client, "root@example.com")
    delete_resp = await client.delete(f"/api/agents/{agent_id}", headers=super_headers)
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/agents/{agent_id}", headers=super_headers)
    assert get_resp.status_code == 404


async def test_support_agent_only_sees_assigned_agents(client: AsyncClient, db_session: AsyncSession):
    await _make_admin(db_session, "admin5@example.com")
    admin_headers = await _login(client, "admin5@example.com")

    agent1 = (
        await client.post("/api/agents", json={"name": "Agent1", "company_name": "C1"}, headers=admin_headers)
    ).json()
    agent2 = (
        await client.post("/api/agents", json={"name": "Agent2", "company_name": "C2"}, headers=admin_headers)
    ).json()

    support_user = await _create_user(
        db_session, email="support2@example.com", password="CorrectHorse123!", role_name=UserRole.SUPPORT_AGENT.value
    )
    db_session.add(OperatorAssignment(user_id=support_user.id, agent_id=agent1["id"]))
    await db_session.commit()

    support_headers = await _login(client, "support2@example.com")

    list_resp = await client.get("/api/agents", headers=support_headers)
    assert list_resp.status_code == 200
    ids = {a["id"] for a in list_resp.json()["items"]}
    assert agent1["id"] in ids
    assert agent2["id"] not in ids

    forbidden_resp = await client.get(f"/api/agents/{agent2['id']}", headers=support_headers)
    assert forbidden_resp.status_code == 403


async def test_branding_logo_upload_rejects_non_image(client: AsyncClient, db_session: AsyncSession):
    await _make_admin(db_session, "admin6@example.com")
    headers = await _login(client, "admin6@example.com")

    agent = (
        await client.post("/api/agents", json={"name": "AgentX", "company_name": "CX"}, headers=headers)
    ).json()

    files = {"file": ("not_an_image.txt", io.BytesIO(b"plain text content"), "text/plain")}
    resp = await client.post(f"/api/agents/{agent['id']}/branding/logo", files=files, headers=headers)
    assert resp.status_code == 400


async def test_branding_logo_upload_accepts_valid_png(client: AsyncClient, db_session: AsyncSession):
    await _make_admin(db_session, "admin7@example.com")
    headers = await _login(client, "admin7@example.com")

    agent = (
        await client.post("/api/agents", json={"name": "AgentY", "company_name": "CY"}, headers=headers)
    ).json()

    # Minimal valid 1x1 PNG.
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"file": ("logo.png", io.BytesIO(png_bytes), "image/png")}
    resp = await client.post(f"/api/agents/{agent['id']}/branding/logo", files=files, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["logo_url"].startswith("/media/agents/")
