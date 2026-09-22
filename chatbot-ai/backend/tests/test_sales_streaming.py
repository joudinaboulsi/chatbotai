from types import SimpleNamespace

import pytest

from app.core import llm
from app.services import sales_ai_service


def _visitor():
    return SimpleNamespace(name=None, email=None, phone=None)


def _tool_call():
    return llm.StreamedToolCall("call_1", "get_packages", "{}")


@pytest.mark.asyncio
async def test_prose_from_tool_rounds_is_kept(monkeypatch):
    rounds = [
        ("Let me pull the UAE rates.", [_tool_call()]),
        ("They start at 0.02 USD.", []),
    ]

    async def fake_complete_with_tools(**kwargs):
        text, calls = rounds.pop(0)
        await llm.emit(text)
        return text, calls

    async def fake_run_tool(*args, **kwargs):
        return {"packages": []}

    monkeypatch.setattr(llm, "complete_with_tools", fake_complete_with_tools)
    monkeypatch.setattr(sales_ai_service, "_run_tool", fake_run_tool)

    streamed: list[str] = []

    async def sink(piece: str) -> None:
        streamed.append(piece)

    llm.set_token_sink(sink)
    try:
        reply = await sales_ai_service.answer_sales_message(
            None,
            agent=None,
            branding=None,
            conversation=None,
            visitor=_visitor(),
            visitor_message="how much is SMS to UAE?",
            history=[],
            rag_context_block=None,
            locale="en",
        )
    finally:
        llm.set_token_sink(None)

    assert "Let me pull the UAE rates." in reply
    assert "They start at 0.02 USD." in reply
    assert "".join(streamed) == reply
