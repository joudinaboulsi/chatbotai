"""Conversation state machine:

    AI_ACTIVE --(visitor asks for a human / AI can't help)--> WAITING_FOR_AGENT
    WAITING_FOR_AGENT --(operator accepts)--> HUMAN_ACTIVE
    HUMAN_ACTIVE --(operator resolves)--> RESOLVED
    RESOLVED/AI_ACTIVE --(operator closes)--> CLOSED

Within AI_ACTIVE, an anonymous prospect's turns are entirely owned by
app.services.sales_flow_service (name/business/use-case/volume/etc.
collection through to a package recommendation) once handle_visitor_message
below has ruled out an account-specific question. A visitor identified via
the dashboard's widget login token isn't a prospect — they keep the older
Sales/Support/Reporting menu and its own lighter name/email/phone
collection, implicit in which of visitor.name/email/phone are still NULL.
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent, AgentBranding
from app.models.conversation import Conversation, Message, Visitor
from app.models.enums import ConversationStatus, LeadSource, MessageSender, SmscSessionStatus
from app.services import lead_detection, rag_service, sales_flow_service, smsc_ai_service, smsc_service
from app.services.handoff_service import request_handoff
from app.services.lead_service import create_or_get_lead

logger = logging.getLogger("app.conversation")

_OPEN_STATUSES = (ConversationStatus.AI_ACTIVE, ConversationStatus.WAITING_FOR_AGENT, ConversationStatus.HUMAN_ACTIVE)

# Every fixed (non-AI-generated) string the widget shows a visitor is kept
# bilingual here — English/Arabic — keyed by an id. `locale` is detected
# per-request from the Accept-Language header the browser already sends
# with every fetch() (see app.api.routes.widget._detect_locale), so no
# widget.js changes were needed to make this work. AI-generated content
# (RAG answers, SMSC tool-calling answers) is out of scope here — the
# SMSC assistant is already instructed to reply in the visitor's language,
# and RAG answers reflect whatever language the knowledge base is in.
_DEFAULT_LOCALE = "en"


def _t(strings: dict[str, str], locale: str) -> str:
    return strings.get(locale, strings[_DEFAULT_LOCALE])


_STR = {
    "greeting_user": {
        "en": "Hello {name}, how can I help you today?",
        "ar": "مرحباً {name}، كيف يمكنني مساعدتك اليوم؟",
    },
    "greeting_support": {
        "en": "Hello {name}, how can I help you look into a customer issue today?",
        "ar": "مرحباً {name}، كيف يمكنني مساعدتك في متابعة مشكلة أحد العملاء اليوم؟",
    },
    "ask_name": {
        "en": "Before we continue, may I have your name?",
        "ar": "قبل أن نتابع، هل يمكنني معرفة اسمك؟",
    },
    "invalid_name": {
        "en": "Sorry, I didn't catch a valid name — could you tell me your name?",
        "ar": "عذراً، لم أفهم اسماً صحيحاً — هل يمكنك إخباري باسمك؟",
    },
    "ask_email": {
        "en": "Nice to meet you, {name}! What is your email address?",
        "ar": "سعدت بلقائك، {name}! ما هو بريدك الإلكتروني؟",
    },
    "invalid_email": {
        "en": "That doesn't look like a valid email address — could you double check it?",
        "ar": "لا يبدو هذا بريداً إلكترونياً صحيحاً — هل يمكنك التحقق منه؟",
    },
    "ask_phone": {
        "en": "Thank you. What is your phone number?",
        "ar": "شكراً لك. ما هو رقم هاتفك؟",
    },
    "invalid_phone": {
        "en": "That doesn't look like a valid phone number — could you double check it?",
        "ar": "لا يبدو هذا رقم هاتف صحيحاً — هل يمكنك التحقق منه؟",
    },
    "collection_done": {
        "en": "Thank you! How can I help you today?",
        "ar": "شكراً لك! كيف يمكنني مساعدتك اليوم؟",
    },
    "handoff_connected": {
        "en": "You've been connected to our support queue. An agent will join shortly.",
        "ar": "تم توصيلك بقائمة انتظار الدعم لدينا. سينضم إليك أحد الموظفين قريباً.",
    },
    "handoff_declined": {
        "en": "No problem — how else can I help you today?",
        "ar": "لا مشكلة — كيف يمكنني مساعدتك بطريقة أخرى؟",
    },
    "explicit_handoff_offer": {
        "en": "Would you like me to connect you with a support agent?",
        "ar": "هل ترغب أن أوصلك بأحد موظفي الدعم؟",
    },
    "support_other_offer": {
        "en": "Sure — let's get you connected with the right person to help.",
        "ar": "بالتأكيد — دعني أوصلك بالشخص المناسب لمساعدتك.",
    },
    "continue_ai_prompt": {
        "en": "Sure — what else can I help you with?",
        "ar": "بالتأكيد — بماذا يمكنني مساعدتك أيضاً؟",
    },
    "account_ready_prompt": {
        "en": "How can I help you with your account today?",
        "ar": "كيف يمكنني مساعدتك في حسابك اليوم؟",
    },
    "session_switched": {
        "en": "Your SMSC account session has been ended. Please provide the username you'd like to use.",
        "ar": "تم إنهاء جلسة حسابك. يرجى تزويدي باسم المستخدم الذي ترغب باستخدامه.",
    },
    "sales_menu_prompt": {
        "en": "Which product are you interested in?",
        "ar": "ما هو المنتج الذي يهمك؟",
    },
    "support_menu_prompt": {
        "en": "Sure — what do you need help with?",
        "ar": "بالتأكيد، بماذا يمكنني مساعدتك؟",
    },
    "reporting_menu_prompt": {
        "en": "Which report would you like?",
        "ar": "ما هو التقرير الذي ترغب به؟",
    },
    "choose_option_hint": {
        "en": "Please choose an option below, or just type your question.",
        "ar": "يرجى اختيار أحد الخيارات أدناه، أو كتابة سؤالك مباشرة.",
    },
}

# The widget's post-greeting quick-reply menu. Leaf options are handled in
# _handle_quick_reply below; category options (menu_sales/menu_support/
# menu_reporting) just branch to another quick-replies message. Values are
# opaque routing keys sent back by the widget — never shown to the visitor,
# who only ever sees the localized `label`.
_ROOT_MENU = [
    {"label": {"en": "Sales", "ar": "المبيعات"}, "value": "menu_sales"},
    {"label": {"en": "Support", "ar": "الدعم الفني"}, "value": "menu_support"},
    {"label": {"en": "Reporting", "ar": "التقارير"}, "value": "menu_reporting"},
    {"label": {"en": "Talk to a human agent", "ar": "التحدث مع وكيل بشري"}, "value": "menu_human"},
]
_SALES_MENU = [
    {"label": {"en": "SMPP", "ar": "SMPP"}, "value": "sales_smpp"},
    {"label": {"en": "HLR Lookup", "ar": "استعلام HLR"}, "value": "sales_hlr"},
    {"label": {"en": "HTTP API", "ar": "واجهة HTTP API"}, "value": "sales_api"},
    {"label": {"en": "Bulk SMS Campaign", "ar": "حملة رسائل SMS جماعية"}, "value": "sales_campaign"},
]
_SUPPORT_MENU = [
    {"label": {"en": "Message ID not found", "ar": "لم يتم العثور على معرف الرسالة"}, "value": "support_msgid"},
    {"label": {"en": "Delivery report issue", "ar": "مشكلة في تقرير التسليم"}, "value": "support_delivery_report"},
    {"label": {"en": "API/SMPP connection issue", "ar": "مشكلة في الاتصال عبر API/SMPP"}, "value": "support_api_smpp"},
    {"label": {"en": "Billing & balance", "ar": "الفواتير والرصيد"}, "value": "support_billing"},
    {"label": {"en": "Other", "ar": "أخرى"}, "value": "support_other"},
]
_REPORTING_MENU = [
    {"label": {"en": "Delivery Report", "ar": "تقرير التسليم"}, "value": "reporting_delivery"},
    {"label": {"en": "Campaign Report", "ar": "تقرير الحملة"}, "value": "reporting_campaign"},
    {"label": {"en": "Account/Balance Report", "ar": "تقرير الحساب/الرصيد"}, "value": "reporting_balance"},
    {"label": {"en": "Custom Report", "ar": "تقرير مخصص"}, "value": "reporting_custom"},
]

# Sales/support leaves are expanded into this canned text and handled
# exactly like a typed visitor question in handle_visitor_message: first
# offered to the SMSC account tool-calling pipeline (smsc_ai_service),
# which answers from the visitor's real account data, falling back to the
# knowledge-base RAG pipeline only if that doesn't claim the question. The
# support ones are phrased to line up with smsc_ai_service._ACCOUNT_KEYWORDS
# so they're recognized as account-specific rather than falling straight
# through to RAG (which has no notion of any one visitor's account).
#
# "support_msgid" is deliberately vague about which message — it just
# nudges the visitor to name one. smsc_ai_service.get_smsc_own_message_status
# is scoped to the visitor's own account (unlike the support-only
# get_smsc_message_status), so once they reply with an id it's answered
# for real instead of just being offered a human.
_SALES_QUESTIONS = {
    "sales_smpp": "Can you tell me about your SMPP service?",
    "sales_hlr": "Can you tell me about your HLR Lookup service?",
    "sales_api": "Can you tell me about your HTTP API service?",
    "sales_campaign": "I'd like to send a bulk SMS campaign, around 1000 SMS — can you tell me about that?",
}
_SUPPORT_QUESTIONS = {
    "support_msgid": "One of my messages wasn't sent — can you check its status? I'll give you the message id.",
    "support_delivery_report": "Can you check my delivery rate — how many of my messages were delivered vs failed recently?",
    "support_api_smpp": "I'm having trouble connecting via SMPP — can you check my SMPP status and my connection?",
    "support_billing": "I have a question about my billing — can you check my account balance?",
}

# Reporting leaves are real account-data questions, not KB questions — they
# go through the same SMSC tool-calling pipeline as Support (get_smsc_
# delivery_stats / get_smsc_traffic / get_smsc_balance), not a straight
# handoff, so a visitor gets the live number instead of just being told
# someone will get back to them.
_REPORTING_QUESTIONS = {
    "reporting_delivery": "Can you check my delivery rate — how many of my messages were delivered vs failed recently?",
    "reporting_campaign": "Can you show me my SMS traffic and usage report for the last 30 days?",
    "reporting_balance": "Can you check my account balance and account status?",
    "reporting_custom": "I'd like a custom report from my account — can you help me pull that?",
}


def _localize_options(options: list[dict], locale: str) -> list[dict]:
    return [{"label": _t(opt["label"], locale), "value": opt["value"]} for opt in options]


def _menu_message(conversation_id: uuid.UUID, content: str, options: list[dict], locale: str) -> Message:
    return Message(
        conversation_id=conversation_id,
        sender_type=MessageSender.AI,
        content=content,
        message_metadata={"type": "quick_replies", "options": _localize_options(options, locale)},
    )


# Appended to every genuine AI answer (RAG or SMSC tool-calling) so the
# visitor is always offered a way to escalate instead of having to know to
# type "talk to sales" or "talk to support" themselves. Deliberately not
# added to menu messages (already have their own options), handoff offers
# (already have their own yes/no), or mid-flow prompts like "what's your
# name/email/username" (those aren't answers, and re-answering the prompt
# is the point — a menu there would be a distraction, not a helpful exit).
# "Live Agent" reuses menu_human's existing immediate-handoff routing —
# it's a shortcut past the Support submenu, not a new code path.
_FOLLOW_UP_OPTIONS = [
    {"label": {"en": "Talk to Sales", "ar": "التحدث مع المبيعات"}, "value": "menu_sales"},
    {"label": {"en": "Talk to Support", "ar": "التحدث مع الدعم الفني"}, "value": "menu_support"},
    {"label": {"en": "Continue with AI", "ar": "المتابعة مع الذكاء الاصطناعي"}, "value": "continue_ai"},
    {"label": {"en": "Live Agent", "ar": "وكيل مباشر"}, "value": "menu_human"},
]


def _with_follow_up(metadata: dict, locale: str) -> dict:
    return {**metadata, "options": _localize_options(_FOLLOW_UP_OPTIONS, locale)}


async def get_or_create_visitor(
    db: AsyncSession,
    *,
    agent_id: uuid.UUID,
    session_token: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[Visitor, str]:
    if session_token:
        result = await db.execute(
            select(Visitor).where(Visitor.agent_id == agent_id, Visitor.session_token == session_token)
        )
        visitor = result.scalar_one_or_none()
        if visitor is not None:
            visitor.last_seen_at = datetime.now(timezone.utc)
            await db.flush()
            return visitor, session_token

    new_token = secrets.token_urlsafe(32)
    visitor = Visitor(
        agent_id=agent_id, session_token=new_token, ip_address=ip_address, user_agent=user_agent
    )
    db.add(visitor)
    await db.flush()
    return visitor, new_token


async def get_or_create_conversation(
    db: AsyncSession, *, agent: Agent, visitor: Visitor
) -> tuple[Conversation, bool]:
    """Returns (conversation, is_new). Building the actual greeting message
    is the caller's job (see build_greeting_message) — it needs the chance
    to silently identify a dashboard-logged-in visitor first, since a
    support-role login gets a different greeting and skips the consumer
    menu entirely."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.visitor_id == visitor.id, Conversation.status.in_(_OPEN_STATUSES))
        .order_by(Conversation.started_at.desc())
    )
    conversation = result.scalars().first()
    if conversation is not None:
        return conversation, False

    conversation = Conversation(agent_id=agent.id, visitor_id=visitor.id, status=ConversationStatus.AI_ACTIVE)
    db.add(conversation)
    await db.flush()
    return conversation, True


async def build_greeting_message(
    db: AsyncSession,
    *,
    conversation: Conversation,
    locale: str,
    name: str | None,
    is_support: bool,
) -> Message:
    """The greeting and the root quick-reply menu are a single message —
    one bubble with the buttons attached directly, not a separate "how can
    I help you" follow-up. A support-role login gets just the greeting,
    tailored to looking into a customer's issue, with no consumer menu:
    Sales/Support/Reporting are for customers, not for support staff.

    A visitor identified via the dashboard login token (name is not None)
    is an existing customer, not a prospect, and keeps this menu-driven
    greeting. A genuinely anonymous visitor (name is None — no login
    token, or it didn't identify anyone) is a prospect: they get the
    sales_flow_service greeting instead, which already asks for their
    name inline, so no menu is attached here at all — see
    app.services.sales_flow_service for what happens next."""
    if name is not None:
        key = "greeting_support" if is_support else "greeting_user"
        content = _t(_STR[key], locale).format(name=name)
        if is_support:
            metadata = {}
        else:
            # Spells out that the buttons are the point, not just decoration
            # — without this, a visitor's first message can be silence, since
            # nothing in the bubble tells them the options below are clickable.
            content = content + "\n\n" + _t(_STR["choose_option_hint"], locale)
            metadata = {"type": "quick_replies", "options": _localize_options(_ROOT_MENU, locale)}
    else:
        content = sales_flow_service.greeting_text(locale)
        metadata = {}

    msg = Message(conversation_id=conversation.id, sender_type=MessageSender.AI, content=content, message_metadata=metadata)
    db.add(msg)
    conversation.last_message_at = datetime.now(timezone.utc)
    await db.flush()
    return msg


async def _next_collection_prompt(visitor: Visitor, locale: str) -> str | None:
    """Still used by the old Sales/Support/Reporting menu's canned-question
    path (login_token-identified "user"-role customers) as a defensive
    check — in practice always already satisfied, since any visitor who
    can reach that menu is, by construction, already_smsc_identified from
    their first message. Anonymous prospects no longer go through this at
    all; see app.services.sales_flow_service for their name/email
    collection instead."""
    if visitor.name is None:
        return _t(_STR["ask_name"], locale)
    if visitor.email is None:
        return _t(_STR["ask_email"], locale).format(name=visitor.name)
    if visitor.phone is None:
        return _t(_STR["ask_phone"], locale)
    return None


async def handle_visitor_message(
    db: AsyncSession,
    *,
    agent: Agent,
    branding: AgentBranding,
    conversation: Conversation,
    visitor: Visitor,
    text: str,
    quick_reply: str | None = None,
    locale: str = _DEFAULT_LOCALE,
) -> list[Message]:
    visitor_msg = Message(conversation_id=conversation.id, sender_type=MessageSender.VISITOR, content=text)
    db.add(visitor_msg)
    conversation.last_message_at = datetime.now(timezone.utc)
    await db.flush()

    if conversation.status != ConversationStatus.AI_ACTIVE:
        # Human is (or will be) handling it — the AI stays quiet so it
        # doesn't talk over the operator.
        return []

    reply_messages: list[Message] = []

    # A visitor silently identified via the Laravel dashboard's widget login
    # token (see app.services.smsc_service.identify_from_widget_login_token)
    # is already a known, authenticated SMSC customer, not an anonymous lead
    # — skip the name/email/phone lead-collection interrogation for them.
    smsc_session_row = await smsc_service.get_session(db, conversation.id)
    already_smsc_identified = (
        smsc_session_row is not None and smsc_session_row.status == SmscSessionStatus.AUTHENTICATED
    )

    # A quick-reply click on a Sales/Support leaf isn't handled as a canned
    # answer of its own — it's expanded into the equivalent free-text
    # question and fed through the *same* pipeline below (SMSC account
    # tools first, then RAG) that a visitor typing that question would hit.
    # That's what lets e.g. "API/SMPP connection issue" get answered from
    # the visitor's real, authenticated account status via smsc_ai_service
    # instead of falling into the generic knowledge-base's "no answer"
    # fallback, which has no notion of any one visitor's account.
    if quick_reply is not None and quick_reply.startswith("sf_"):
        # A button from the public sales conversation flow (use-case,
        # conversion, "just looking" shortcuts) — entirely owned by
        # sales_flow_service, never mixed with the old menu system below.
        return await sales_flow_service.handle_sales_step(
            db, agent=agent, branding=branding, conversation=conversation, visitor=visitor,
            text=text, quick_reply=quick_reply, locale=locale,
        )

    if quick_reply is not None:
        canned_question = (
            _SALES_QUESTIONS.get(quick_reply) or _SUPPORT_QUESTIONS.get(quick_reply) or _REPORTING_QUESTIONS.get(quick_reply)
        )
        if canned_question is not None:
            if not already_smsc_identified:
                next_prompt = await _next_collection_prompt(visitor, locale)
                if next_prompt is not None:
                    # Still owed name/email/phone — a click carries no free
                    # text of its own to (mis)parse as the answer to that
                    # (validate_name() would happily accept the canned
                    # question sentence itself as a "name"), so just ask
                    # again. The visitor can click the button a second time
                    # once they've finished, landing them straight past this
                    # check into the SMSC/RAG handling below.
                    msg = Message(conversation_id=conversation.id, sender_type=MessageSender.AI, content=next_prompt)
                    db.add(msg)
                    await db.flush()
                    return [msg]
            text = canned_question
            if quick_reply in _SALES_QUESTIONS:
                await create_or_get_lead(
                    db, agent=agent, visitor=visitor, conversation=conversation, source=LeadSource.CONTACT_SALES_REQUEST
                )
        else:
            # Category buttons and "talk to a human" are fully self-contained
            # menu actions, not questions — handled directly, bypassing the
            # name/email/phone gate and SMSC/RAG below.
            menu_reply = await _handle_quick_reply(
                db, agent=agent, conversation=conversation, visitor=visitor, quick_reply=quick_reply, locale=locale
            )
            if menu_reply is not None:
                return menu_reply

    smsc_reply = await _handle_smsc_message(
        db, agent=agent, conversation=conversation, visitor=visitor, text=text, locale=locale
    )
    if smsc_reply is not None:
        return smsc_reply

    if quick_reply is None and not already_smsc_identified:
        # A genuinely anonymous prospect's free text — not a login_token-
        # identified existing customer (those keep the old menu below via
        # canned_question), and not an account-specific question (already
        # claimed by _handle_smsc_message above). The public sales
        # conversation flow owns name/email collection and everything else
        # from here; see app.services.sales_flow_service.
        return await sales_flow_service.handle_sales_step(
            db, agent=agent, branding=branding, conversation=conversation, visitor=visitor,
            text=text, quick_reply=None, locale=locale,
        )

    lead_source = lead_detection.detect_lead_source(text)
    if lead_source is not None:
        await create_or_get_lead(db, agent=agent, visitor=visitor, conversation=conversation, source=lead_source)

    if lead_detection.is_explicit_handoff_request(text):
        offer_msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.AI,
            content=_t(_STR["explicit_handoff_offer"], locale),
            message_metadata={"type": "handoff_offer"},
        )
        db.add(offer_msg)
        reply_messages.append(offer_msg)
        await db.flush()
        return reply_messages

    history = await _recent_history(db, conversation.id)
    try:
        reply_text, chunks_used = await rag_service.generate_reply(
            db, agent=agent, branding=branding, visitor_message=text, history=history
        )
    except Exception:
        # An upstream LLM failure must not propagate: the route commits
        # after this call, so a 500 here would roll back the visitor's own
        # message along with the reply, losing it from the transcript.
        logger.exception("RAG reply generation failed for conversation %s", conversation.id)
        reply_text, chunks_used = rag_service.NO_ANSWER_FALLBACK, []

    if reply_text == rag_service.NO_ANSWER_FALLBACK:
        offer_msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.AI,
            content=reply_text,
            message_metadata={"type": "handoff_offer"},
        )
        db.add(offer_msg)
        reply_messages.append(offer_msg)
        await db.flush()
        return reply_messages

    ai_msg = Message(
        conversation_id=conversation.id,
        sender_type=MessageSender.AI,
        content=reply_text,
        message_metadata=_with_follow_up({"chunk_ids": [str(c.id) for c in chunks_used]}, locale),
    )
    db.add(ai_msg)
    reply_messages.append(ai_msg)
    await db.flush()
    return reply_messages


async def _handle_quick_reply(
    db: AsyncSession,
    *,
    agent: Agent,
    conversation: Conversation,
    visitor: Visitor,
    quick_reply: str,
    locale: str,
) -> list[Message] | None:
    """Routes a widget quick-reply button click that is a self-contained
    menu action (category navigation, human handoff) rather than a question
    — real questions (Sales/Support/Reporting leaves) are expanded to their
    canned question text and handled by the caller instead. Returns the
    reply message(s), or None if `quick_reply` isn't a value this menu
    system knows about (caller falls back to treating the message as
    free text)."""

    if quick_reply == "menu_sales":
        msg = _menu_message(conversation.id, _t(_STR["sales_menu_prompt"], locale), _SALES_MENU, locale)
        db.add(msg)
        await db.flush()
        return [msg]

    if quick_reply == "menu_support":
        msg = _menu_message(conversation.id, _t(_STR["support_menu_prompt"], locale), _SUPPORT_MENU, locale)
        db.add(msg)
        await db.flush()
        return [msg]

    if quick_reply == "menu_reporting":
        msg = _menu_message(conversation.id, _t(_STR["reporting_menu_prompt"], locale), _REPORTING_MENU, locale)
        db.add(msg)
        await db.flush()
        return [msg]

    if quick_reply == "menu_human":
        await request_handoff(db, agent=agent, visitor=visitor, conversation=conversation)
        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.SYSTEM,
            content=_t(_STR["handoff_connected"], locale),
        )
        db.add(msg)
        await db.flush()
        return [msg]

    if quick_reply == "continue_ai":
        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.AI,
            content=_t(_STR["continue_ai_prompt"], locale),
        )
        db.add(msg)
        await db.flush()
        return [msg]

    if quick_reply == "support_other":
        # Deliberately vague — no tool or KB lookup answers "something
        # else", so skip straight to offering a human instead of wasting
        # a round trip on a guaranteed no-answer.
        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.AI,
            content=_t(_STR["support_other_offer"], locale),
            message_metadata={"type": "handoff_offer"},
        )
        db.add(msg)
        await db.flush()
        return [msg]

    return None


async def _handle_smsc_message(
    db: AsyncSession, *, agent: Agent, conversation: Conversation, visitor: Visitor, text: str, locale: str
) -> list[Message] | None:
    """Returns the reply message(s) if this turn was handled as an SMSC
    account matter, or None if the caller should fall through to the
    normal public RAG path. SMSC account data and the PDF/URL knowledge
    base are never blended in the same lookup — only the same reply, when
    a question asks for both (see smsc_ai_service.answer_account_question,
    which is handed RAG context purely as reference material)."""

    if not await smsc_service.is_enabled(db):
        return None

    if smsc_ai_service.is_credential_request(text):
        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.AI,
            content=smsc_ai_service.CREDENTIAL_DEFLECTION,
            message_metadata=_with_follow_up({}, locale),
        )
        db.add(msg)
        await db.flush()
        return [msg]

    session_row = await smsc_service.get_session(db, conversation.id)

    if session_row is not None and session_row.status == SmscSessionStatus.PENDING:
        result = await smsc_service.validate_and_authenticate(
            db, session_row=session_row, username=text.strip(), conversation_id=conversation.id
        )
        if not result.ok:
            msg = Message(conversation_id=conversation.id, sender_type=MessageSender.AI, content=result.message)
            db.add(msg)
            await db.flush()
            return [msg]

        reply_messages = [
            Message(conversation_id=conversation.id, sender_type=MessageSender.AI, content=result.message)
        ]
        if result.pending_question:
            history = await _recent_history(db, conversation.id)
            rag_context = await rag_service.get_context_block(db, agent.id, result.pending_question)
            answer = await smsc_ai_service.answer_account_question(
                db,
                session_row=session_row,
                conversation_id=conversation.id,
                visitor_message=result.pending_question,
                history=history,
                rag_context_block=rag_context,
            )
            reply_messages.append(
                Message(
                    conversation_id=conversation.id,
                    sender_type=MessageSender.AI,
                    content=answer,
                    message_metadata=_with_follow_up({}, locale),
                )
            )
        else:
            reply_messages.append(
                Message(
                    conversation_id=conversation.id,
                    sender_type=MessageSender.AI,
                    content=_t(_STR["account_ready_prompt"], locale),
                )
            )
        for m in reply_messages:
            db.add(m)
        await db.flush()
        return reply_messages

    if session_row is not None and session_row.status == SmscSessionStatus.AUTHENTICATED:
        if smsc_ai_service.is_switch_request(text):
            await smsc_service.terminate_session(db, session_row)
            msg = Message(
                conversation_id=conversation.id,
                sender_type=MessageSender.AI,
                content=_t(_STR["session_switched"], locale),
            )
            db.add(msg)
            await db.flush()
            return [msg]

        # Once authenticated, every message goes through the tool-calling
        # handler rather than being pre-filtered by the account-specific
        # keyword list: it has both RAG context and the account tools
        # available and decides for itself whether a question needs a
        # tool call, so a verified visitor can ask about anything on
        # their account without depending on exact keyword phrasing.
        history = await _recent_history(db, conversation.id)
        rag_context = await rag_service.get_context_block(db, agent.id, text)
        answer = await smsc_ai_service.answer_account_question(
            db,
            session_row=session_row,
            conversation_id=conversation.id,
            visitor_message=text,
            history=history,
            rag_context_block=rag_context,
        )
        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.AI,
            content=answer,
            message_metadata=_with_follow_up({}, locale),
        )
        db.add(msg)
        await db.flush()
        return [msg]

    if smsc_ai_service.is_account_specific(text):
        await smsc_service.start_pending(
            db, conversation_id=conversation.id, visitor_id=visitor.id, pending_question=text
        )
        msg = Message(
            conversation_id=conversation.id, sender_type=MessageSender.AI, content=smsc_ai_service.ASK_USERNAME_MESSAGE
        )
        db.add(msg)
        await db.flush()
        return [msg]

    return None


async def _recent_history(db: AsyncSession, conversation_id: uuid.UUID, limit: int = 12) -> list[tuple[str, str]]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    role_map = {
        MessageSender.VISITOR: "user",
        MessageSender.AI: "assistant",
        MessageSender.OPERATOR: "assistant",
        
    }
    return [(role_map[m.sender_type], m.content) for m in messages if m.sender_type in role_map]


async def handle_handoff_choice(
    db: AsyncSession,
    *,
    agent: Agent,
    conversation: Conversation,
    visitor: Visitor,
    accepted: bool,
    locale: str = _DEFAULT_LOCALE,
) -> Message:
    if accepted:
        await request_handoff(db, agent=agent, visitor=visitor, conversation=conversation)
        reply = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.SYSTEM,
            content=_t(_STR["handoff_connected"], locale),
        )
    else:
        reply = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.AI,
            content=_t(_STR["handoff_declined"], locale),
        )
    db.add(reply)
    conversation.last_message_at = datetime.now(timezone.utc)
    await db.flush()
    return reply
