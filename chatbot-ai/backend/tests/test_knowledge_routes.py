import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.services import task_dispatch
from tests.test_auth import _create_user

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str = "CorrectHorse123!") -> dict[str, str]:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _admin_headers(client: AsyncClient, db_session: AsyncSession, email: str) -> dict[str, str]:
    await _create_user(db_session, email=email, password="CorrectHorse123!", role_name=UserRole.ADMIN.value)
    return await _login(client, email)


async def test_list_knowledge_bases(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session, "kblistadmin@example.com")
    await client.post(
        "/api/knowledge-bases", json={"name": "KB One", "source_type": "pdf", "agent_ids": []}, headers=headers
    )
    await client.post(
        "/api/knowledge-bases", json={"name": "KB Two", "source_type": "pdf", "agent_ids": []}, headers=headers
    )

    resp = await client.get("/api/knowledge-bases", headers=headers)
    assert resp.status_code == 200
    names = {kb["name"] for kb in resp.json()}
    assert {"KB One", "KB Two"}.issubset(names)


async def test_create_knowledge_base_and_assign_agent(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session, "kbadmin1@example.com")

    agent_resp = await client.post(
        "/api/agents", json={"name": "Agent1", "company_name": "C1"}, headers=headers
    )
    agent_id = agent_resp.json()["id"]

    kb_resp = await client.post(
        "/api/knowledge-bases",
        json={"name": "Docs KB", "description": "Product docs", "source_type": "pdf", "agent_ids": [agent_id]},
        headers=headers,
    )
    
    assert kb_resp.status_code == 201, kb_resp.text
    kb = kb_resp.json()
    assert kb["agent_ids"] == [agent_id]

    get_resp = await client.get(f"/api/knowledge-bases/{kb['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Docs KB"


async def test_upload_pdf_creates_pending_document_and_dispatches_task(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    headers = await _admin_headers(client, db_session, "kbadmin2@example.com")
    kb_resp = await client.post("/api/knowledge-bases", json={"name": "KB", "source_type": "pdf", "agent_ids": []}, headers=headers)
    kb_id = kb_resp.json()["id"]

    dispatched = []
    monkeypatch.setattr(task_dispatch, "dispatch_document_processing", lambda doc_id: dispatched.append(doc_id))

    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R>>endobj\ntrailer<</Root 1 0 R>>"
    )
    files = {"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    resp = await client.post(f"/api/knowledge-bases/{kb_id}/pdf", files=files, headers=headers)
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["status"] == "pending"
    assert doc["file_name"] == "doc.pdf"
    assert len(dispatched) == 1

    list_resp = await client.get(f"/api/knowledge-bases/{kb_id}/documents", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_upload_non_pdf_rejected(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session, "kbadmin3@example.com")
    kb_resp = await client.post("/api/knowledge-bases", json={"name": "KB", "source_type": "pdf", "agent_ids": []}, headers=headers)
    kb_id = kb_resp.json()["id"]

    files = {"file": ("doc.txt", io.BytesIO(b"just some text"), "text/plain")}
    resp = await client.post(f"/api/knowledge-bases/{kb_id}/pdf", files=files, headers=headers)
    assert resp.status_code == 400


async def test_create_scrape_job_dispatches_task(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    headers = await _admin_headers(client, db_session, "kbadmin4@example.com")
    kb_resp = await client.post("/api/knowledge-bases", json={"name": "KB", "source_type": "website", "agent_ids": []}, headers=headers)
    kb_id = kb_resp.json()["id"]
    

    dispatched = []
    monkeypatch.setattr(task_dispatch, "dispatch_site_processing", lambda site_id: dispatched.append(site_id))

    resp = await client.post(
        f"/api/knowledge-bases/{kb_id}/scrape",
        json={
            "url": "https://example.com",
            "mode": "crawl",
            "max_pages": 10,
            "max_depth": 2,
            "include_subpages": True,
            "exclude_urls": ["/admin"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    site = resp.json()
    assert site["status"] == "pending"
    assert site["mode"] == "crawl"
    assert len(dispatched) == 1

    list_resp = await client.get(f"/api/knowledge-bases/{kb_id}/scraped-sites", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_support_agent_cannot_manage_knowledge_bases(client: AsyncClient, db_session: AsyncSession):
    await _create_user(
        db_session, email="kbsupport@example.com", password="CorrectHorse123!", role_name=UserRole.SUPPORT_AGENT.value
    )
    headers = await _login(client, "kbsupport@example.com")

    resp = await client.post("/api/knowledge-bases", json={"name": "KB", "source_type": "pdf", "agent_ids": []}, headers=headers)
    assert resp.status_code == 403


async def test_cannot_upload_pdf_to_website_type_kb(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session, "kbadmin6@example.com")
    kb_resp = await client.post(
        "/api/knowledge-bases", json={"name": "KB", "source_type": "website", "agent_ids": []}, headers=headers
    )
    kb_id = kb_resp.json()["id"]

    pdf_bytes = b"%PDF-1.4\ntrailer<</Root 1 0 R>>"
    files = {"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    resp = await client.post(f"/api/knowledge-bases/{kb_id}/pdf", files=files, headers=headers)
    assert resp.status_code == 400


async def test_cannot_create_scrape_on_pdf_type_kb(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session, "kbadmin7@example.com")
    kb_resp = await client.post(
        "/api/knowledge-bases", json={"name": "KB", "source_type": "pdf", "agent_ids": []}, headers=headers
    )
    kb_id = kb_resp.json()["id"]

    resp = await client.post(
        f"/api/knowledge-bases/{kb_id}/scrape",
        json={"url": "https://example.com", "mode": "single_url", "max_pages": 1, "max_depth": 1, "include_subpages": False, "exclude_urls": []},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_delete_document_removes_it(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    headers = await _admin_headers(client, db_session, "kbadmin5@example.com")
    kb_resp = await client.post("/api/knowledge-bases", json={"name": "KB", "source_type": "pdf", "agent_ids": []}, headers=headers)
    kb_id = kb_resp.json()["id"]

    monkeypatch.setattr(task_dispatch, "dispatch_document_processing", lambda doc_id: None)
    pdf_bytes = b"%PDF-1.4\ntrailer<</Root 1 0 R>>"
    files = {"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    upload_resp = await client.post(f"/api/knowledge-bases/{kb_id}/pdf", files=files, headers=headers)
    doc_id = upload_resp.json()["id"]

    delete_resp = await client.delete(f"/api/knowledge-bases/{kb_id}/documents/{doc_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = await client.get(f"/api/knowledge-bases/{kb_id}/documents", headers=headers)
    assert list_resp.json() == []

