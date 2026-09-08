"""End-to-end WebSocket test using Starlette's synchronous TestClient,
deliberately kept separate from the async httpx-based fixtures in
conftest.py: TestClient drives the app on its own event loop via a
background thread, and mixing that with the shared asyncpg-bound
`db_session` fixture's loop would break the connection pool. Seeding is
done via the real seed script (a separate process), so there's no shared
engine/event-loop state between setup and the TestClient run either.
"""

import os
import subprocess
import sys

import pytest
from starlette.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.filterwarnings("ignore")


def _seed_admin(email: str, password: str) -> None:
    env = os.environ.copy()
    env["ADMIN_EMAIL"] = email
    env["ADMIN_PASSWORD"] = password
    result = subprocess.run(
        [sys.executable, "-m", "app.workers.seed"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert result.returncode == 0, f"seed failed: {result.stdout}\n{result.stderr}"


def test_websocket_rejects_invalid_token():
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/api/ws/notifications?token=not-a-real-token"):
                pass


def test_websocket_delivers_live_agent_request_notification():
    _seed_admin("wsadmin@example.com", "WsAdmin123!")

    with TestClient(app) as client:
        login_resp = client.post(
            "/api/auth/login", json={"email": "wsadmin@example.com", "password": "WsAdmin123!"}
        )
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]

        agent_resp = client.post(
            "/api/agents",
            json={"name": "WS Agent", "company_name": "WSCo"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert agent_resp.status_code == 201
        agent_id = agent_resp.json()["id"]

        with client.websocket_connect(f"/api/ws/notifications?token={access_token}") as ws:
            session_resp = client.post(f"/api/widget/{agent_id}/session", json={})
            assert session_resp.status_code == 200
            token = session_resp.json()["session_token"]

            client.post(f"/api/widget/{agent_id}/message", json={"session_token": token, "message": "Hi there!"})
            client.post(f"/api/widget/{agent_id}/message", json={"session_token": token, "message": "Dana"})
            client.post(
                f"/api/widget/{agent_id}/message", json={"session_token": token, "message": "dana@example.com"}
            )
            client.post(
                f"/api/widget/{agent_id}/message", json={"session_token": token, "message": "+12025550199"}
            )
            handoff_resp = client.post(
                f"/api/widget/{agent_id}/handoff", json={"session_token": token, "accepted": True}
            )
            assert handoff_resp.status_code == 200

            # Accepting the handoff triggers both a lead upsert and a live
            # agent request — two pushes, in that order (see
            # handoff_service.request_handoff).
            lead_payload = ws.receive_json()
            assert lead_payload["type"] == "new_lead"
            assert "Dana" in lead_payload["title"]

            handoff_payload = ws.receive_json()
            assert handoff_payload["type"] == "live_agent_request"
            assert "Dana" in handoff_payload["title"]
