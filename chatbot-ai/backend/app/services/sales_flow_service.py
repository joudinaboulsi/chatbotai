"""Entry point for the public sales conversation (anonymous prospects).
The actual discovery/recommendation/objection-handling/closing behavior
lives in app.services.sales_ai_service — an adaptive, tool-calling LLM
agent, not a fixed question sequence, per the "professional SMSC Sales
Agent" spec it implements. This module is a thin wrapper: it owns the
bilingual greeting text, the one explicit-handoff fast path worth
bypassing the LLM for, and lightweight lead-source tagging on keyword
matches — everything else (what to ask, when to recommend, how to
handle objections, when to close) is the model's call, grounded in real
package data via sales_ai_service's get_packages tool so it never
invents a price or feature.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentBranding
from app.models.conversation import Conversation, Message, Visitor
from app.models.enums import MessageSender
from app.services import lead_detection, rag_service, sales_ai_service
from app.services.handoff_service import request_handoff
from app.services.lead_service import create_or_get_lead

_DEFAULT_LOCALE = "en"


def _t(strings: dict[str, str], locale: str) -> str:
    return strings.get(locale, strings[_DEFAULT_LOCALE])


_STR = {
    "sales_greeting": {
        "en": "Hi! \U0001F44B Welcome! I'm here to help you find the right SMS solution for your business. May I know your name, and what type of business or work you're in?",
        "ar": "مرحباً! \U0001F44B أهلاً بك! أنا هنا لمساعدتك في إيجاد حل الرسائل النصية المناسب لعملك. هل يمكنني معرفة اسمك، ونوع عملك أو نشاطك التجاري؟",
    },
    "human_connected": {
        "en": "You've been connected to our support queue. An agent will join shortly.",
        "ar": "تم توصيلك بقائمة انتظار الدعم لدينا. سينضم إليك أحد الموظفين قريباً.",
    },
}


def greeting_text(locale: str) -> str:
    return _t(_STR["sales_greeting"], locale)


async def _recent_history(db: AsyncSession, conversation_id, limit: int = 10) -> list[tuple[str, str]]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    role_map = {MessageSender.VISITOR: "user", MessageSender.AI: "assistant", MessageSender.OPERATOR: "assistant"}
    return [(role_map[m.sender_type], m.content) for m in messages if m.sender_type in role_map]


async def handle_sales_step(
    db: AsyncSession,
    *,
    agent: Agent,
    branding: AgentBranding,
    conversation: Conversation,
    visitor: Visitor,
    text: str,
    quick_reply: str | None,
    locale: str,
) -> list[Message]:
    # An explicit "talk to a human" request is unambiguous enough to skip
    # the LLM round trip entirely and connect immediately.
    if lead_detection.is_explicit_handoff_request(text):
        await request_handoff(db, agent=agent, visitor=visitor, conversation=conversation)
        msg = Message(
            conversation_id=conversation.id, sender_type=MessageSender.SYSTEM, content=_t(_STR["human_connected"], locale)
        )
        db.add(msg)
        await db.flush()
        return [msg]

    # Early, low-signal interest tagging (idempotent per conversation) —
    # the model's own request_sales_contact tool call captures a much more
    # specific source once the customer actually commits, but this catches
    # the first "pricing"/"demo"/etc. mention even if they never get there.
    lead_source = lead_detection.detect_lead_source(text)
    if lead_source is not None:
        await create_or_get_lead(db, agent=agent, visitor=visitor, conversation=conversation, source=lead_source)

    history = await _recent_history(db, conversation.id)
    rag_context = await rag_service.get_context_block(db, agent.id, text)
    answer = await sales_ai_service.answer_sales_message(
        db,
        agent=agent,
        branding=branding,
        conversation=conversation,
        visitor=visitor,
        visitor_message=text,
        history=history,
        rag_context_block=rag_context,
        locale=locale,
    )
    msg = Message(conversation_id=conversation.id, sender_type=MessageSender.AI, content=answer)
    db.add(msg)
    await db.flush()
    return [msg]
