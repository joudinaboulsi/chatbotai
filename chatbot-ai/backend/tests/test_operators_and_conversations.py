import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from tests.test_auth import _create_user

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str = "CorrectHorse123!") -> dict[str, str]:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _admin_headers(client: AsyncClient, db_session: AsyncSession, email: str) -> dict[str, str]:
    await _create_user(db_session, email=email, password="CorrectHorse123!", role_name=UserRole.ADMIN.value)
    return await _login(client, email)


async def _super_headers(client: AsyncClient, db_session: AsyncSession, email: str) -> dict[str, str]:
    await _create_user(db_session, email=email, password="CorrectHorse123!", role_name=UserRole.SUPER_ADMIN.value)
    return await _login(client, email)


async def test_create_operator_and_assign_agent(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session, "opadmin1@example.com")
    agent = (await client.post("/api/agents", json={"name": "A1", "company_name": "C1"}, headers=headers)).json()

    resp = await client.post(
        "/api/operators",
        json={
            "name": "Support One",
            "email": "support-op1@example.com",
            "password": "SupportPass123!",
            "role": "support_agent",
            "assigned_agent_ids": [agent["id"]],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    operator = resp.json()
    assert operator["role"] == "support_agent"
    assert operator["assigned_agent_ids"] == [agent["id"]]

    support_headers = await _login(client, "support-op1@example.com", "SupportPass123!")
    list_resp = await client.get("/api/agents", headers=support_headers)
    ids = {a["id"] for a in list_resp.json()["items"]}
    assert agent["id"] in ids


async def test_admin_cannot_create_super_admin(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session, "opadmin2@example.com")
    resp = await client.post(
        "/api/operators",
        json={
            "name": "Wannabe Root",
            "email": "wannabe@example.com",
            "password": "Password123!",
            "role": "super_admin",
        },
        headers=headers,
    )
    assert resp.status_code == 403


async def test_duplicate_operator_email_conflict(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session, "opadmin3@example.com")
    payload = {
        "name": "Dup",
        "email": "dup-op@example.com",
        "password": "Password123!",
        "role": "support_agent",
    }
    first = await client.post("/api/operators", json=payload, headers=headers)
    assert first.status_code == 201
    second = await client.post("/api/operators", json=payload, headers=headers)
    assert second.status_code == 409


async def test_operator_cannot_delete_self(client: AsyncClient, db_session: AsyncSession):
    headers = await _super_headers(client, db_session, "rootself@example.com")
    me_resp = await client.get("/api/auth/me", headers=headers)
    my_id = me_resp.json()["id"]

    resp = await client.delete(f"/api/operators/{my_id}", headers=headers)
    assert resp.status_code == 400


async def test_conversation_list_and_operator_message_flow(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from app.services import embedding_service

    async def fake_embed(texts):
        return [[0.001] * 1536 for _ in texts]

    monkeypatch.setattr(embedding_service, "embed_texts", fake_embed)

    headers = await _admin_headers(client, db_session, "convadmin1@example.com")
    agent = (await client.post("/api/agents", json={"name": "A2", "company_name": "C2"}, headers=headers)).json()

    session = (await client.post(f"/api/widget/{agent['id']}/session", json={})).json()
    conv_id = session["conversation_id"]

    list_resp = await client.get("/api/conversations", headers=headers)
    assert list_resp.status_code == 200
    assert any(c["id"] == conv_id for c in list_resp.json()["items"])

    detail_resp = await client.get(f"/api/conversations/{conv_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert len(detail_resp.json()["messages"]) >= 1

    # Operator can't post a message until the conversation is waiting/human active.
    msg_resp = await client.post(f"/api/conversations/{conv_id}/messages", json={"content": "hi"}, headers=headers)
    assert msg_resp.status_code == 400

    resolve_resp = await client.post(f"/api/conversations/{conv_id}/resolve", headers=headers)
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"


async def test_dashboard_stats_reflect_real_data(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from app.services import embedding_service

    async def fake_embed(texts):
        return [[0.001] * 1536 for _ in texts]

    monkeypatch.setattr(embedding_service, "embed_texts", fake_embed)

    headers = await _admin_headers(client, db_session, "dashadmin1@example.com")
    agent = (await client.post("/api/agents", json={"name": "A3", "company_name": "C3"}, headers=headers)).json()

    await client.post(f"/api/widget/{agent['id']}/session", json={})

    stats_resp = await client.get("/api/dashboard/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_conversations"] >= 1
    assert stats["active_conversations"] >= 1

    charts_resp = await client.get("/api/dashboard/charts", headers=headers)
    assert charts_resp.status_code == 200


async def test_email_settings_update_and_get_never_leaks_password(client: AsyncClient, db_session: AsyncSession):
    headers = await _super_headers(client, db_session, "emailsuper1@example.com")

    update_resp = await client.put(
        "/api/settings/email",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "noreply@example.com",
            "smtp_password": "supersecret",
            "encryption": "tls",
            "from_name": "Support",
            "from_email": "noreply@example.com",
            "support_email": "support@example.com",
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    body = update_resp.json()
    assert "smtp_password" not in body
    assert body["is_configured"] is True

    get_resp = await client.get("/api/settings/email", headers=headers)
    assert "smtp_password" not in get_resp.json()


async def test_audit_log_requires_super_admin(client: AsyncClient, db_session: AsyncSession):
    admin_headers = await _admin_headers(client, db_session, "auditadmin1@example.com")
    resp = await client.get("/api/audit-logs", headers=admin_headers)
    assert resp.status_code == 403

    super_headers = await _super_headers(client, db_session, "auditsuper1@example.com")
    resp2 = await client.get("/api/audit-logs", headers=super_headers)
    assert resp2.status_code == 200
    assert resp2.json()["total"] >= 1
