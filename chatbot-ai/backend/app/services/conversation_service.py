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
    "support_other_describe": {
        "en": "Of course. Please describe the issue you're experiencing, and I'll help you troubleshoot it.",
        "ar": "بالتأكيد. يرجى وصف المشكلة التي تواجهها وسأساعدك في حلها.",
    },
    "continue_ai_prompt": {
        "en": "Sure — what else can I help you with?",
        "ar": "بالتأكيد — بماذا يمكنني مساعدتك أيضاً؟",
    },
    "session_switched": {
        "en": "Your SMSC account session has been ended. Please log in with the account you'd like to use, then ask me again.",
        "ar": "تم إنهاء جلسة حسابك. يرجى تسجيل الدخول بالحساب الذي ترغب باستخدامه ثم اسألني مرة أخرى.",
    },
    "sales_menu_prompt": {
        "en": "Which product are you interested in?",
        "ar": "ما هو المنتج الذي يهمك؟",
    },
    "support_menu_prompt": {
        "en": "Sure — what do you need help with?",
        "ar": "بالتأكيد، بماذا يمكنني مساعدتك؟",
    },
    "support_connection_menu_prompt": {
        "en": "Which connection or service issue?",
        "ar": "ما هي مشكلة الاتصال أو الخدمة؟",
    },
    "support_sending_menu_prompt": {
        "en": "Which sending or delivery issue?",
        "ar": "ما هي مشكلة الإرسال أو التسليم؟",
    },
    "support_senderid_menu_prompt": {
        "en": "Is this about a Sender ID or about routing/coverage?",
        "ar": "هل هذا بخصوص معرف المرسل أم التوجيه/التغطية؟",
    },
    "support_account_menu_prompt": {
        "en": "Is this about your account or about billing?",
        "ar": "هل هذا بخصوص حسابك أم الفواتير؟",
    },
    "support_reporting_menu_prompt": {
        "en": "Which lookup or report do you need?",
        "ar": "ما هو الاستعلام أو التقرير الذي تحتاجه؟",
    },
    "support_other_menu_prompt": {
        "en": "What kind of technical issue is it?",
        "ar": "ما نوع المشكلة التقنية؟",
    },
    "reporting_menu_prompt": {
        "en": "Which report would you like?",
        "ar": "ما هو التقرير الذي ترغب به؟",
    },
    "human_reason_prompt": {
        "en": "Sure. Is this regarding Sales, Support, Billing, Account, or something else?",
        "ar": "بالتأكيد. هل هذا بخصوص المبيعات أم الدعم الفني أم الفواتير أم الحساب أم شيء آخر؟",
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
# Two-level support menu: this top-level list is categories only (each
# branches to a _SUPPORT_SUBMENUS entry below); "Other issue" (free text,
# classified by the AI) and "Talk to a human agent" (routes into the
# existing menu_human — see _handle_quick_reply) are always reachable so a
# customer is never stuck without an escape hatch.
_SUPPORT_MENU = [
    {"label": {"en": "Connection & Service Status", "ar": "الاتصال وحالة الخدمة"}, "value": "support_cat_connection"},
    {"label": {"en": "Sending & Delivery", "ar": "الإرسال والتسليم"}, "value": "support_cat_sending"},
    {"label": {"en": "Sender ID & Routing", "ar": "معرف المرسل والتوجيه"}, "value": "support_cat_senderid"},
    {"label": {"en": "Account & Billing", "ar": "الحساب والفواتير"}, "value": "support_cat_account"},
    {"label": {"en": "Reporting & Lookups", "ar": "التقارير والاستعلامات"}, "value": "support_cat_reporting"},
    {"label": {"en": "Technical / Other", "ar": "تقني / أخرى"}, "value": "support_cat_other"},
    {"label": {"en": "Talk to a human agent", "ar": "التحدث مع وكيل بشري"}, "value": "menu_human"},
]
# "Back" always routes to menu_support — reuses the existing top-level
# handler rather than needing its own case in _handle_quick_reply.
_SUPPORT_BACK_OPTION = {"label": {"en": "Back", "ar": "رجوع"}, "value": "menu_support"}
_SUPPORT_SUBMENUS: dict[str, list[dict]] = {
    "support_cat_connection": [
        {"label": {"en": "SMPP connection issue", "ar": "مشكلة في اتصال SMPP"}, "value": "support_smpp"},
        {"label": {"en": "HTTP API issue", "ar": "مشكلة في HTTP API"}, "value": "support_http_api"},
        {"label": {"en": "HLR issue", "ar": "مشكلة في HLR"}, "value": "support_hlr"},
        {"label": {"en": "IP whitelist issue", "ar": "مشكلة في قائمة IP المسموح بها"}, "value": "support_ip_whitelist"},
        _SUPPORT_BACK_OPTION,
    ],
    "support_cat_sending": [
        {"label": {"en": "SMS delivery issue", "ar": "مشكلة في تسليم الرسائل"}, "value": "support_sms_delivery"},
        {"label": {"en": "Delivery report (DLR)", "ar": "تقرير التسليم (DLR)"}, "value": "support_dlr"},
        {"label": {"en": "OTP / transactional SMS issue", "ar": "مشكلة في رسائل OTP / المعاملات"}, "value": "support_otp"},
        {"label": {"en": "Campaign issue", "ar": "مشكلة في الحملة"}, "value": "support_campaign"},
        _SUPPORT_BACK_OPTION,
    ],
    "support_cat_senderid": [
        {"label": {"en": "Sender ID issue", "ar": "مشكلة في معرف المرسل"}, "value": "support_sender_id"},
        {"label": {"en": "Routing / country coverage", "ar": "التوجيه / التغطية الدولية"}, "value": "support_routing"},
        _SUPPORT_BACK_OPTION,
    ],
    "support_cat_account": [
        {"label": {"en": "Account / login issue", "ar": "مشكلة في الحساب / تسجيل الدخول"}, "value": "support_account_login"},
        {"label": {"en": "Billing / balance / package", "ar": "الفواتير / الرصيد / الباقة"}, "value": "support_billing"},
        _SUPPORT_BACK_OPTION,
    ],
    "support_cat_reporting": [
        {"label": {"en": "Message ID / message status", "ar": "معرف الرسالة / حالة الرسالة"}, "value": "support_msgid"},
        {"label": {"en": "Reporting / statistics", "ar": "التقارير / الإحصائيات"}, "value": "support_reporting_stats"},
        _SUPPORT_BACK_OPTION,
    ],
    "support_cat_other": [
        {"label": {"en": "Integration / technical issue", "ar": "مشكلة تقنية / تكامل"}, "value": "support_integration"},
        {"label": {"en": "Other issue", "ar": "مشكلة أخرى"}, "value": "support_other"},
        _SUPPORT_BACK_OPTION,
    ],
}
_SUPPORT_SUBMENU_PROMPTS: dict[str, str] = {
    "support_cat_connection": "support_connection_menu_prompt",
    "support_cat_sending": "support_sending_menu_prompt",
    "support_cat_senderid": "support_senderid_menu_prompt",
    "support_cat_account": "support_account_menu_prompt",
    "support_cat_reporting": "support_reporting_menu_prompt",
    "support_cat_other": "support_other_menu_prompt",
}
_REPORTING_MENU = [
    {"label": {"en": "Delivery Report", "ar": "تقرير التسليم"}, "value": "reporting_delivery"},
    {"label": {"en": "Campaign Report", "ar": "تقرير الحملة"}, "value": "reporting_campaign"},
    {"label": {"en": "Account/Balance Report", "ar": "تقرير الحساب/الرصيد"}, "value": "reporting_balance"},
    {"label": {"en": "Custom Report", "ar": "تقرير مخصص"}, "value": "reporting_custom"},
]

# Progressive-disclosure drill-down buttons attached to a traffic/delivery
# report's reply (see smsc_ai_service._build_report_extras' "show_actions"
# and _handle_smsc_message below) — each re-enters the exact same
# SMSC-tool-calling pipeline as any typed question, just with wording
# steered at a specific tool (get_smsc_traffic_breakdown /
# get_smsc_failure_analysis), not a separate code path.
_REPORT_ACTIONS = [
    {"label": {"en": "Traffic Trend", "ar": "اتجاه الحركة"}, "value": "report_traffic_trend"},
    {"label": {"en": "Failure Analysis", "ar": "تحليل الفشل"}, "value": "report_failure_analysis"},
    {"label": {"en": "By Country", "ar": "حسب الدولة"}, "value": "report_by_country"},
    {"label": {"en": "By Sender ID", "ar": "حسب معرف المرسل"}, "value": "report_by_sender_id"},
]
_REPORT_ACTION_QUESTIONS = {
    "report_traffic_trend": "Can you show me my SMS traffic report for the last 30 days again?",
    "report_failure_analysis": (
        "Can you give me a failure analysis of my messages for the last 30 days — broken down by reason, "
        "country, and sender ID, with the largest failure category highlighted?"
    ),
    "report_by_country": "Can you break down my SMS traffic by destination country for the last 30 days?",
    "report_by_sender_id": "Can you break down my SMS traffic by sender ID for the last 30 days?",
}

# Shown when a visitor asks for a human agent, before the handoff is
# actually created — lets the operator picking it up from the dashboard
# see at a glance what it's about (see _HUMAN_REASON_LABELS, passed as
# handoff_service.request_handoff's `reason`) instead of only "Live agent
# requested: <name>" with no context.
_HUMAN_REASON_MENU = [
    {"label": {"en": "Sales", "ar": "المبيعات"}, "value": "human_reason_sales"},
    {"label": {"en": "Support", "ar": "الدعم الفني"}, "value": "human_reason_support"},
    {"label": {"en": "Billing", "ar": "الفواتير"}, "value": "human_reason_billing"},
    {"label": {"en": "Account", "ar": "الحساب"}, "value": "human_reason_account"},
    {"label": {"en": "Something else", "ar": "شيء آخر"}, "value": "human_reason_other"},
]
_HUMAN_REASON_LABELS = {
    "human_reason_sales": "Sales",
    "human_reason_support": "Support",
    "human_reason_billing": "Billing",
    "human_reason_account": "Account",
    "human_reason_other": "Other",
}

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
# "Bulk SMS Campaign" is a use-case, not a real row in the services table —
# kept as its own option appended after the DB-driven catalog below rather
# than folded into it.
_SALES_CAMPAIGN_OPTION = _SALES_MENU[-1]


async def _build_sales_menu(db: AsyncSession, conversation_id: uuid.UUID) -> list[dict]:
    """The Sales menu must list every real product (webapp's `services`
    table — see SmscAccountController::services), not a hand-maintained
    subset that silently goes stale as products are added. Falls back to
    the static _SALES_MENU if the SMSC integration is disabled/unreachable
    so the widget still shows something rather than an empty menu."""
    catalog = await smsc_service.get_services_public(db, conversation_id=conversation_id)
    if not catalog:
        return _SALES_MENU
    options = [
        {"label": {"en": item["name"], "ar": item["name"]}, "value": f"sales_{item['slug']}"}
        for item in catalog
        if item.get("slug") and item.get("name")
    ]
    options.append(_SALES_CAMPAIGN_OPTION)
    return options


async def _resolve_sales_catalog_question(db: AsyncSession, conversation_id: uuid.UUID, quick_reply: str) -> str | None:
    """Expands a sales_<slug> leaf that isn't one of the hand-phrased
    _SALES_QUESTIONS (i.e. anything beyond SMPP/HLR/API/campaign) into a
    generic canned question, by matching the slug back against the same
    catalog _build_sales_menu used to offer it."""
    slug = quick_reply[len("sales_"):]
    catalog = await smsc_service.get_services_public(db, conversation_id=conversation_id) or []
    match = next((item for item in catalog if item.get("slug") == slug), None)
    if match is None:
        return None
    return f"Can you tell me about your {match['name']} service?"
_SUPPORT_QUESTIONS = {
    "support_sms_delivery": "Some of my SMS messages aren't being delivered — can you help me check what's happening?",
    "support_msgid": "One of my messages wasn't sent — can you check its status? I'll give you the message id.",
    "support_dlr": "I'm not getting delivery reports (DLR) for my messages, or the status looks wrong — can you check?",
    "support_http_api": "I'm having trouble with the HTTP API — can you check my HTTP API status and configuration?",
    "support_smpp": "I'm having trouble connecting via SMPP — can you check my SMPP status and my connection?",
    "support_sender_id": "I have an issue with one of my sender IDs — can you help me check it?",
    "support_campaign": "I'm having a problem with an SMS campaign — can you help me check it?",
    "support_otp": "My OTP or transactional messages aren't arriving, or are delayed — can you help me check?",
    "support_account_login": "I'm having trouble with my account or logging in — can you help me check my account status?",
    "support_billing": "I have a question about my billing — can you check my account balance?",
    "support_reporting_stats": "Can you show me my messaging statistics — sent, delivered, and failed counts?",
    "support_integration": "I'm having a technical or integration issue with the SMSC platform — can you help me check?",
    "support_hlr": "I'm having an issue with HLR lookups — can you check my HLR status?",
    "support_ip_whitelist": "My IP address isn't being accepted, or I need to add a new one — can you check my current allowed IPs?",
    "support_routing": "I have a question about routing or country coverage for my messages — can you help?",
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
# "Live Agent" reuses menu_human's existing reason-then-handoff routing —
# it's a shortcut past the Support submenu, not a new code path.
_FOLLOW_UP_OPTIONS = [
    {"label": {"en": "Talk to Sales", "ar": "التحدث مع المبيعات"}, "value": "menu_sales"},
    {"label": {"en": "Support Menu", "ar": "قائمة الدعم"}, "value": "menu_support"},
    {"label": {"en": "Continue with AI", "ar": "المتابعة مع الذكاء الاصطناعي"}, "value": "continue_ai"},
    {"label": {"en": "Human Support", "ar": "دعم بشري"}, "value": "menu_human"},
]


def _with_follow_up(metadata: dict, locale: str, *, is_support: bool = False) -> dict:
    options = (
        [opt for opt in _FOLLOW_UP_OPTIONS if opt["value"] != "menu_sales"]
        if is_support
        else _FOLLOW_UP_OPTIONS
    )
    return {**metadata, "options": _localize_options(options, locale)}


def _with_report(metadata: dict, report: dict | None, locale: str) -> dict:
    """Copies smsc_ai_service.answer_account_question's structured `report`
    (chart/stats/peak/low/progress/breakdown — all computed server-side
    from real tool data, never model text) onto a reply's metadata, plus
    the drill-down action buttons when the report came from a top-level
    traffic/delivery-stats call (see _build_report_extras' show_actions)."""
    if not report:
        return metadata
    for key in ("header", "chart", "stats", "peak", "low", "progress", "breakdown"):
        if report.get(key):
            metadata[key] = report[key]
    if report.get("show_actions"):
        metadata["report_actions"] = _localize_options(_REPORT_ACTIONS, locale)
    return metadata


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
    # Support staff aren't a sales prospect — never offer them "Talk to
    # Sales" in the post-answer follow-up row (see _with_follow_up).
    is_support_session = already_smsc_identified and smsc_session_row.role == "support"

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
            _SALES_QUESTIONS.get(quick_reply)
            or _SUPPORT_QUESTIONS.get(quick_reply)
            or _REPORTING_QUESTIONS.get(quick_reply)
            or _REPORT_ACTION_QUESTIONS.get(quick_reply)
        )
        if canned_question is None and quick_reply.startswith("sales_"):
            canned_question = await _resolve_sales_catalog_question(db, conversation.id, quick_reply)
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
            if quick_reply in _SALES_QUESTIONS or quick_reply.startswith("sales_"):
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
        db, agent=agent, conversation=conversation, visitor=visitor, text=text, locale=locale,
        is_support=is_support_session,
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
        message_metadata=_with_follow_up(
            {"chunk_ids": [str(c.id) for c in chunks_used]}, locale, is_support=is_support_session
        ),
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
        sales_menu = await _build_sales_menu(db, conversation.id)
        msg = _menu_message(conversation.id, _t(_STR["sales_menu_prompt"], locale), sales_menu, locale)
        db.add(msg)
        await db.flush()
        return [msg]

    if quick_reply == "menu_support":
        msg = _menu_message(conversation.id, _t(_STR["support_menu_prompt"], locale), _SUPPORT_MENU, locale)
        db.add(msg)
        await db.flush()
        return [msg]

    if quick_reply in _SUPPORT_SUBMENUS:
        prompt_key = _SUPPORT_SUBMENU_PROMPTS[quick_reply]
        msg = _menu_message(conversation.id, _t(_STR[prompt_key], locale), _SUPPORT_SUBMENUS[quick_reply], locale)
        db.add(msg)
        await db.flush()
        return [msg]


    if quick_reply == "menu_reporting":
        msg = _menu_message(conversation.id, _t(_STR["reporting_menu_prompt"], locale), _REPORTING_MENU, locale)
        db.add(msg)
        await db.flush()
        return [msg]

    if quick_reply == "menu_human":
        msg = _menu_message(conversation.id, _t(_STR["human_reason_prompt"], locale), _HUMAN_REASON_MENU, locale)
        db.add(msg)
        await db.flush()
        return [msg]

    if quick_reply in _HUMAN_REASON_LABELS:
        await request_handoff(
            db, agent=agent, visitor=visitor, conversation=conversation, reason=_HUMAN_REASON_LABELS[quick_reply]
        )
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
        # Not a canned question — the customer doesn't need to know or pick
        # a technical category. Their next free-text reply is handled by
        # the normal pipeline below (_handle_smsc_message's authenticated
        # branch), which already has both the account tools and RAG context
        # to classify and troubleshoot whatever they describe.
        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.AI,
            content=_t(_STR["support_other_describe"], locale),
        )
        db.add(msg)
        await db.flush()
        return [msg]

    return None


async def _handle_smsc_message(
    db: AsyncSession, *, agent: Agent, conversation: Conversation, visitor: Visitor, text: str, locale: str,
    is_support: bool = False,
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
            message_metadata=_with_follow_up({}, locale, is_support=is_support),
        )
        db.add(msg)
        await db.flush()
        return [msg]

    session_row = await smsc_service.get_session(db, conversation.id)

    # There is deliberately no "type your username to authenticate" path
    # here. A username alone identifies an account but proves nothing —
    # the only way a session becomes AUTHENTICATED is a real login on the
    # website, which hands the widget a signed login_token that
    # smsc_service.identify_from_widget_login_token exchanges for identity
    # (see the widget login_token handling earlier in handle_visitor_
    # message). A guest with no such token who asks an account-specific
    # question just gets told to log in — see the is_account_specific
    # branch at the end of this function.

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

        if lead_detection.is_explicit_handoff_request(text):
            # An authenticated session's messages are otherwise always
            # claimed by the tool-calling handler below, which has no tool
            # for "talk to a human" and would just answer conversationally
            # instead of ever escalating. Returning None here instead lets
            # the caller's existing explicit_handoff_offer flow (below, in
            # handle_visitor_message) pick it up like it already does for
            # unauthenticated visitors.
            return None

        # Once authenticated, every message goes through the tool-calling
        # handler rather than being pre-filtered by the account-specific
        # keyword list: it has both RAG context and the account tools
        # available and decides for itself whether a question needs a
        # tool call, so a verified visitor can ask about anything on
        # their account without depending on exact keyword phrasing.
        history = await _recent_history(db, conversation.id)
        rag_context = await rag_service.get_context_block(db, agent.id, text)
        answer, report = await smsc_ai_service.answer_account_question(
            db,
            session_row=session_row,
            conversation_id=conversation.id,
            visitor_message=text,
            history=history,
            rag_context_block=rag_context,
        )
        if answer == smsc_ai_service.UNAVAILABLE_MESSAGE:
            metadata = {"type": "handoff_offer"}
        else:
            metadata = _with_report(_with_follow_up({}, locale, is_support=is_support), report, locale)
        msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSender.AI,
            content=answer,
            message_metadata=metadata,
        )
        db.add(msg)
        await db.flush()
        return [msg]

    if smsc_ai_service.is_account_specific(text):
        msg = Message(
            conversation_id=conversation.id, sender_type=MessageSender.AI, content=smsc_ai_service.LOGIN_REQUIRED_MESSAGE
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
