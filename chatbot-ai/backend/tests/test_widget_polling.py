import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.services import embedding_service
from tests.test_auth import _create_user

pytestmark = pytest.mark.asyncio


def _fake_embed(dim: int = 1536):
    async def _embed(texts):
        return [[0.001] * dim for _ in texts]

    return _embed


async def _admin_headers(client: AsyncClient, db_session: AsyncSession, email: str) -> dict[str, str]:
    await _create_user(db_session, email=email, password="CorrectHorse123!", role_name=UserRole.ADMIN.value)
    resp = await client.post("/api/auth/login", json={"email": email, "password": "CorrectHorse123!"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_poll_returns_operator_message_after_handoff(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    monkeypatch.setattr(embedding_service, "embed_texts", _fake_embed())
    headers = await _admin_headers(client, db_session, "polladmin1@example.com")
    agent = (await client.post("/api/agents", json={"name": "PollAgent", "company_name": "PC"}, headers=headers)).json()
    agent_id = agent["id"]

    session = (await client.post(f"/api/widget/{agent_id}/session", json={})).json()
    token = session["session_token"]

    baseline = await client.get(f"/api/widget/{agent_id}/messages", params={"session_token": token})
    assert baseline.status_code == 200
    last_id = baseline.json()["messages"][-1]["id"]

    await client.post(f"/api/widget/{agent_id}/message", json={"session_token": token, "message": "Alice"})
    await client.post(f"/api/widget/{agent_id}/message", json={"session_token": token, "message": "alice@example.com"})
    await client.post(f"/api/widget/{agent_id}/message", json={"session_token": token, "message": "+12025550111"})
    await client.post(
        f"/api/widget/{agent_id}/handoff", json={"session_token": token, "accepted": True}
    )

    conv_id = session["conversation_id"]
    operator_resp = await client.post(
        f"/api/conversations/{conv_id}/messages", json={"content": "Hi, this is Sarah from support!"}, headers=headers
    )
    assert operator_resp.status_code == 201

    poll_resp = await client.get(
        f"/api/widget/{agent_id}/messages", params={"session_token": token, "after": last_id}
    )
    assert poll_resp.status_code == 200
    body = poll_resp.json()
    assert body["conversation_status"] == "human_active"
    contents = [m["content"] for m in body["messages"]]
    assert "Hi, this is Sarah from support!" in contents


async def test_poll_with_unknown_session_token_404s(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session, "polladmin2@example.com")
    agent = (await client.post("/api/agents", json={"name": "PollAgent2", "company_name": "PC2"}, headers=headers)).json()

    resp = await client.get(
        f"/api/widget/{agent['id']}/messages", params={"session_token": "not-a-real-token"}
    )
    assert resp.status_code == 404
