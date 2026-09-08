import json
import types
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    ConversationStatus,
    KnowledgeSourceType,
    LiveAgentRequestStatus,
    UserRole,
)
from app.models.knowledge import KnowledgeChunk
from app.models.lead import Lead
from app.models.live_agent import LiveAgentRequest
from app.services import embedding_service, sales_ai_service, smsc_service
from tests.test_auth import _create_user


class _FakeToolCall:
    def __init__(self, id_: str, name: str, arguments: str):
        self.id = id_
        self.function = types.SimpleNamespace(name=name, arguments=arguments)


class _FakeToolMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeToolChoice:
    def __init__(self, message: _FakeToolMessage):
        self.message = message
        self.finish_reason = "tool_calls" if message.tool_calls else "stop"


class _FakeToolCompletion:
    def __init__(self, message: _FakeToolMessage):
        self.choices = [_FakeToolChoice(message)]


class _SequencedFakeCompletions:
    """Returns one pre-built completion per call, in order — for testing
    sales_ai_service's two-completion tool-calling loop (decide -> tool
    result -> synthesize) without a real LLM."""

    def __init__(self, completions: list[_FakeToolCompletion]):
        self._completions = list(completions)

    async def create(self, **kwargs):
        return self._completions.pop(0)


class _SequencedFakeChat:
    def __init__(self, completions: list[_FakeToolCompletion]):
        self.completions = _SequencedFakeCompletions(completions)


class _SequencedFakeOpenAIClient:
    def __init__(self, completions: list[_FakeToolCompletion]):
        self.chat = _SequencedFakeChat(completions)


_FAKE_PACKAGES = [
    {
        "slug": "starter", "name": "Starter", "min_monthly_volume": 0, "max_monthly_volume": 9999,
        "price_amount": None, "currency": "USD", "billing_period": "monthly",
        "coverage_notes": "Core SMS sending.", "features": ["HTTP API access"],
    },
    {
        "slug": "business", "name": "Business", "min_monthly_volume": 10000, "max_monthly_volume": 500000,
        "price_amount": None, "currency": "USD", "billing_period": "monthly",
        "coverage_notes": "SMPP access and priority throughput.", "features": ["HTTP API + SMPP"],
    },
    {
        "slug": "enterprise", "name": "Enterprise", "min_monthly_volume": 500001, "max_monthly_volume": None,
        "price_amount": None, "currency": "USD", "billing_period": "monthly",
        "coverage_notes": "Custom volume commitments.", "features": ["Dedicated SMPP binds"],
    },
]


async def _fake_get_packages(db, *, conversation_id):
    return _FAKE_PACKAGES


pytestmark = pytest.mark.asyncio


def _fake_embed(dim: int = 1536):
    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[0.001] * dim for _ in texts]

    return _embed


async def _make_admin_headers(client: AsyncClient, db_session: AsyncSession, email: str) -> dict[str, str]:
    await _create_user(db_session, email=email, password="CorrectHorse123!", role_name=UserRole.ADMIN.value)
    resp = await client.post("/api/auth/login", json={"email": email, "password": "CorrectHorse123!"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _setup_agent_with_kb(client: AsyncClient, db_session: AsyncSession, monkeypatch, admin_email: str):
    monkeypatch.setattr(embedding_service, "embed_texts", _fake_embed())
    headers = await _make_admin_headers(client, db_session, admin_email)

    agent_resp = await client.post(
        "/api/agents",
        json={"name": "Tawasol Agent", "company_name": "Tawasol", "industry": "Telecommunications"},
        headers=headers,
    )
    agent = agent_resp.json()

    kb_resp = await client.post(
        "/api/knowledge-bases",
        json={"name": "Tawasol KB", "source_type": "website", "agent_ids": [agent["id"]]},
        headers=headers,
    )
    kb_id = kb_resp.json()["id"]

    from app.models.knowledge import KnowledgeBase
    from app.services import knowledge_service

    kb = await knowledge_service.get_knowledge_base(db_session, uuid.UUID(kb_id))
    await knowledge_service._embed_and_store_chunks(
        db_session,
        knowledge_base_id=kb.id,
        document_id=None,
        scraped_page_id=None,
        source_type=KnowledgeSourceType.WEBSITE,
        texts=["Tawasol offers SMS gateway, WhatsApp Business API, and voice services for enterprises."],
    )
    await db_session.commit()

    return agent, headers


async def test_full_visitor_journey(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """Anonymous visitors are prospects: the widget greeting hands them
    straight to the public sales conversation (see
    app.services.sales_ai_service — an adaptive, tool-calling LLM agent,
    not a fixed question sequence) rather than the old Sales/Support/
    Reporting menu (that's only shown to a dashboard-login_token-
    identified existing customer). This exercises the real two-completion
    tool-calling loop end to end: the model calls request_sales_contact,
    which must create a real Lead and a real LiveAgentRequest — not just
    say it did."""
    agent, admin_headers = await _setup_agent_with_kb(client, db_session, monkeypatch, "flowadmin1@example.com")
    agent_id = agent["id"]

    monkeypatch.setattr(smsc_service, "get_packages", _fake_get_packages)

    tool_call_message = _FakeToolMessage(
        content=None,
        tool_calls=[
            _FakeToolCall(
                "call_1",
                "request_sales_contact",
                json.dumps({"name": "John Smith", "email": "john@example.com", "reason": "purchase_request"}),
            )
        ],
    )
    final_message = _FakeToolMessage(content="Great, John! I've connected you with our sales team.")
    monkeypatch.setattr(
        sales_ai_service, "_client",
        lambda: _SequencedFakeOpenAIClient([_FakeToolCompletion(tool_call_message), _FakeToolCompletion(final_message)]),
    )

    config_resp = await client.get(f"/api/widget/config/{agent_id}")
    assert config_resp.status_code == 200
    assert config_resp.json()["company_name"] == "Tawasol"

    session_resp = await client.post(f"/api/widget/{agent_id}/session", json={})
    assert session_resp.status_code == 200
    session = session_resp.json()
    token = session["session_token"]
    assert session["conversation_status"] == "ai_active"
    assert len(session["messages"]) == 1
    assert session["messages"][0]["message_metadata"] == {}

    resp = await client.post(
        f"/api/widget/{agent_id}/message",
        json={"session_token": token, "message": "I'd like to buy SMS credits, my name is John Smith, email john@example.com"},
    )
    assert resp.status_code == 200
    reply = resp.json()["messages"][0]
    assert "sales team" in reply["content"].lower()

    result = await db_session.execute(select(KnowledgeChunk))
    assert len(result.scalars().all()) >= 1

    result = await db_session.execute(select(LiveAgentRequest))
    requests = result.scalars().all()
    assert len(requests) == 1
    assert requests[0].status == LiveAgentRequestStatus.WAITING

    result = await db_session.execute(select(Lead))
    leads = result.scalars().all()
    assert len(leads) == 1
    assert leads[0].name == "John Smith"
    assert leads[0].email == "john@example.com"
    assert leads[0].source.value == "purchase_request"


async def test_explicit_handoff_request_bypasses_llm(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """An unambiguous "talk to a human" request is a fast path in
    sales_flow_service.handle_sales_step — it never calls the LLM at all,
    so no monkeypatching of sales_ai_service is needed here."""
    agent, _ = await _setup_agent_with_kb(client, db_session, monkeypatch, "flowadmin2@example.com")
    agent_id = agent["id"]

    token = (await client.post(f"/api/widget/{agent_id}/session", json={})).json()["session_token"]
    resp = await client.post(
        f"/api/widget/{agent_id}/message",
        json={"session_token": token, "message": "I want to talk to a human agent please"},
    )
    reply = resp.json()["messages"][0]
    assert reply["sender_type"] == "system"

    result = await db_session.execute(select(LiveAgentRequest))
    requests = result.scalars().all()
    assert len(requests) == 1
    assert requests[0].status == LiveAgentRequestStatus.WAITING


async def test_pricing_question_creates_lead(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """A pricing/demo/quote keyword match tags a lead immediately — before
    the LLM even runs — see sales_flow_service.handle_sales_step's
    early lead-source tagging."""
    agent, _ = await _setup_agent_with_kb(client, db_session, monkeypatch, "flowadmin3@example.com")
    agent_id = agent["id"]

    async def _fake_answer(**kwargs):
        return "Pricing depends on your destination and volume — how many messages do you expect to send monthly?"

    monkeypatch.setattr(sales_ai_service, "answer_sales_message", _fake_answer)

    token = (await client.post(f"/api/widget/{agent_id}/session", json={})).json()["session_token"]
    resp = await client.post(
        f"/api/widget/{agent_id}/message", json={"session_token": token, "message": "What is your pricing?"}
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(Lead))
    leads = result.scalars().all()
    assert len(leads) == 1
    assert leads[0].source.value == "pricing_request"


async def test_lead_backfills_contact_info_once_known(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """A lead created early (from a keyword match, before the visitor has
    given any contact info) gets its name/email backfilled once
    request_sales_contact learns them later in the same conversation —
    see lead_service.create_or_get_lead."""
    agent, _ = await _setup_agent_with_kb(client, db_session, monkeypatch, "flowadmin6@example.com")
    agent_id = agent["id"]
    monkeypatch.setattr(smsc_service, "get_packages", _fake_get_packages)

    real_answer_sales_message = sales_ai_service.answer_sales_message

    async def _fake_answer_no_tool(**kwargs):
        return "Sure — how many messages do you expect to send monthly?"

    monkeypatch.setattr(sales_ai_service, "answer_sales_message", _fake_answer_no_tool)

    token = (await client.post(f"/api/widget/{agent_id}/session", json={})).json()["session_token"]
    await client.post(
        f"/api/widget/{agent_id}/message", json={"session_token": token, "message": "Can I get a quote please?"}
    )

    result = await db_session.execute(select(Lead))
    lead = result.scalars().one()
    assert lead.name is None
    assert lead.email is None

    tool_call_message = _FakeToolMessage(
        content=None,
        tool_calls=[
            _FakeToolCall(
                "call_1", "request_sales_contact",
                json.dumps({"name": "Priya", "email": "priya@example.com", "reason": "quote_request"}),
            )
        ],
    )
    final_message = _FakeToolMessage(content="Thanks, Priya — sales will follow up shortly.")
    monkeypatch.setattr(
        sales_ai_service, "_client",
        lambda: _SequencedFakeOpenAIClient([_FakeToolCompletion(tool_call_message), _FakeToolCompletion(final_message)]),
    )
    # Restore the real answer_sales_message (not the _fake_answer_no_tool
    # stub above) so this second turn actually runs the tool-calling loop
    # against the _client we just patched.
    monkeypatch.setattr(sales_ai_service, "answer_sales_message", real_answer_sales_message)

    await client.post(
        f"/api/widget/{agent_id}/message",
        json={"session_token": token, "message": "My name is Priya, email priya@example.com"},
    )

    await db_session.refresh(lead)
    assert lead.name == "Priya"
    assert lead.email == "priya@example.com"

    result = await db_session.execute(select(Lead))
    assert len(result.scalars().all()) == 1  # still one lead, backfilled — not a duplicate


async def test_inactive_agent_widget_returns_404(client: AsyncClient, db_session: AsyncSession):
    headers = await _make_admin_headers(client, db_session, "flowadmin4@example.com")
    agent = (
        await client.post("/api/agents", json={"name": "Inactive Agent", "company_name": "X"}, headers=headers)
    ).json()
    await client.post(f"/api/agents/{agent['id']}/deactivate", headers=headers)

    resp = await client.get(f"/api/widget/config/{agent['id']}")
    assert resp.status_code == 404
    



async def test_reopening_session_reuses_open_conversation(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr(embedding_service, "embed_texts", _fake_embed())
    headers = await _make_admin_headers(client, db_session, "flowadmin5@example.com")
    agent = (
        await client.post("/api/agents", json={"name": "Agent", "company_name": "C"}, headers=headers)
    ).json()

    first = (await client.post(f"/api/widget/{agent['id']}/session", json={})).json()
    second = (
        await client.post(f"/api/widget/{agent['id']}/session", json={"session_token": first["session_token"]})
    ).json()

    assert second["conversation_id"] == first["conversation_id"]
    assert second["session_token"] == first["session_token"]
