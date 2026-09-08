"""Shared OpenAI-compatible client factory.

Clients are cached per (model-purpose) rather than constructed per call —
a fresh AsyncOpenAI builds a fresh httpx connection pool, so per-call
construction meant no connection was ever reused across turns.

The explicit timeout matters more than it looks: the SDK defaults to a
600s timeout with 2 retries, so one hung upstream could pin a visitor's
turn for half an hour before anything gave up.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from functools import lru_cache
from types import SimpleNamespace

from openai import AsyncOpenAI

from app.core.config import settings


@lru_cache
def client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        timeout=settings.OPENAI_REQUEST_TIMEOUT,
        max_retries=0,
    )


def chat_model() -> str:
    """Conversational paths with no tool calling — RAG answers, sales flow."""
    return settings.OPENAI_CHAT_MODEL


def tool_model() -> str:
    """Tool-calling paths. Kept separate because dropping a tool call is a
    wrong answer, not a slow one, and the fastest models are the least
    reliable at emitting every call a question needs."""
    return settings.OPENAI_TOOL_MODEL or settings.OPENAI_CHAT_MODEL


# Widget messages are rendered with textContent (widget.js), so markdown
# reaches visitors as literal asterisks.
PLAIN_TEXT_RULE = (
    "- Reply in plain text. Do not use markdown formatting — no **bold**, no bullet syntax, "
    "no headings. The chat widget renders your reply as plain text."
)


# --- token streaming -------------------------------------------------
# Set by the SSE widget route for the duration of one turn. Services call
# complete_text() and stay unaware of whether anyone is listening, so the
# streaming and non-streaming paths run the exact same conversation code.
_token_sink: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar("llm_token_sink", default=None)


def set_token_sink(sink: Callable[[str], Awaitable[None]] | None) -> None:
    _token_sink.set(sink)


async def complete_text(**kwargs) -> str:
    """A chat completion whose result is prose, not tool calls.

    Streams to the active token sink when there is one, and returns the
    assembled text either way. Never pass tools= here — a streamed tool
    call arrives in fragments this does not reassemble.
    """
    sink = _token_sink.get()
    if sink is None:
        response = await client().chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    parts: list[str] = []
    stream = await client().chat.completions.create(stream=True, **kwargs)
    async for chunk in stream:
        if not chunk.choices:
            continue
        piece = chunk.choices[0].delta.content
        if piece:
            parts.append(piece)
            await sink(piece)
    return "".join(parts)


class StreamedToolCall:
    """Mirrors the SDK's tool-call shape so callers work either way."""

    __slots__ = ("id", "type", "function")

    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)


async def complete_with_tools(**kwargs) -> tuple[str, list]:
    """A completion that may answer in prose OR ask for tool calls.

    Returns (text, tool_calls). When a sink is active the response is
    streamed: prose reaches the visitor token by token, while tool-call
    deltas are reassembled by index and never forwarded — a half-built
    function name is not something anyone should see.
    """
    sink = _token_sink.get()
    if sink is None:
        message = (await client().chat.completions.create(**kwargs)).choices[0].message
        return message.content or "", list(message.tool_calls or [])

    parts: list[str] = []
    pending: dict[int, dict] = {}
    stream = await client().chat.completions.create(stream=True, **kwargs)
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            parts.append(delta.content)
            await sink(delta.content)
        for tc in delta.tool_calls or []:
            slot = pending.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
            if tc.id:
                slot["id"] = tc.id
            if tc.function and tc.function.name:
                slot["name"] += tc.function.name
            if tc.function and tc.function.arguments:
                slot["arguments"] += tc.function.arguments

    calls = [
        StreamedToolCall(s["id"], s["name"], s["arguments"])
        for _, s in sorted(pending.items())
    ]
    return "".join(parts), calls
