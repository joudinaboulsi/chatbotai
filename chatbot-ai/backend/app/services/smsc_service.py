"""SMSCIntegrationService: the only place that turns a validated SMSC
session into actual SMSC API calls. Kept independent from rag_service /
embedding_service — knowledge-base retrieval and SMSC account data are
different sources and never mixed at this layer.

Security invariants enforced here (not just documented — actually enforced
in code):
  - The SMSC user identity used for every account-data call always comes
    from the caller's already-authenticated SmscSession row, never from a
    username/user_id supplied by the visitor or the LLM in that turn.
  - Every field name that looks like a credential (password/secret/token/
    key) is stripped from SMSC API responses before they reach the AI or
    the audit log, in addition to whatever the SMSC API itself withholds.
  - Failures never produce an invented answer — callers get a typed
    exception and must show a fixed, honest message.
"""

import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import smsc_client
from app.core.config import settings as app_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.smsc_client import SmscApiError, SmscConfig, SmscNotFoundError, SmscUnavailableError
from app.models.enums import SmscSessionStatus
from app.models.smsc import SmscApiLog, SmscSession
from app.models.settings import SMSCSettings

logger = logging.getLogger("app.smsc")

_SENSITIVE_KEY_PATTERN = re.compile(r"pass(word)?|secret|token|api[_-]?key|private[_-]?key|credential", re.IGNORECASE)

# name -> (endpoint label for logging, request type, required session role
# or None if any authenticated role may call it)
_TOOL_ENDPOINTS: dict[str, tuple[str, str, str | None]] = {
    "get_smsc_balance": ("/users/{user}/balance", "GET", None),
    "get_smsc_traffic": ("/users/{user}/traffic", "GET", None),
    "get_smsc_delivery_stats": ("/users/{user}/delivery-stats", "GET", None),
    "get_smsc_traffic_breakdown": ("/users/{user}/traffic/breakdown", "GET", None),
    "get_smsc_failure_analysis": ("/users/{user}/failures", "GET", None),
    "get_smsc_connections": ("/users/{user}/connections", "GET", None),
    "get_smsc_sender_ids": ("/users/{user}/sender-ids", "GET", None),
    "get_smsc_account_status": ("/users/{user}/status", "GET", None),
    "get_smsc_smpp_status": ("/users/{user}/smpp-status", "GET", None),
    "get_smsc_http_api_status": ("/users/{user}/http-api-status", "GET", None),
    "get_smsc_hlr_status": ("/users/{user}/hlr-status", "GET", None),
    "get_smsc_dlr_status": ("/users/{user}/dlr-status", "GET", None),
    # User-scoped, unlike get_smsc_message_status below — the API filters
    # by both {user} and message_id, so this only ever returns a message
    # that belongs to the caller's own account. Safe to offer to any role.
    "get_smsc_own_message_status": ("/users/{user}/messages/{message_id}", "GET", None),
    # Not user-scoped (no {user} in the template): looked up by the
    # message_id argument alone. Support-only — see the role check in
    # call_tool below, enforced in code, not just by which tools the AI
    # is offered.
    "get_smsc_message_status": ("/messages/{message_id}", "GET", "support"),
    # Also not user-scoped: same price list regardless of caller. Available
    # to both roles.
    "get_smsc_pricing": ("/pricing", "GET", None),
}

# Every tool above whose endpoint has a {user} placeholder — i.e. scoped to
# the caller's own SMSC account. A support-role session has no SMSC
# account of its own (see smsc_ai_service._SUPPORT_ROLE_INSTRUCTIONS), so
# none of these make sense for it, even though session_row.smsc_user_id is
# still set (to the support staffer's own users.id) and would otherwise
# happily resolve. Enforced here, not just by which tools the AI is
# offered for that role (see smsc_ai_service._tools_for_role).
_ACCOUNT_SCOPED_TOOLS = frozenset(
    name for name, (endpoint, _method, _role) in _TOOL_ENDPOINTS.items() if "{user}" in endpoint
)


async def get_settings_row(db: AsyncSession) -> SMSCSettings | None:
    result = await db.execute(select(SMSCSettings).limit(1))
    return result.scalar_one_or_none()


async def get_or_create_settings_row(db: AsyncSession) -> SMSCSettings:
    row = await get_settings_row(db)
    if row is None:
        row = SMSCSettings(
            api_base_url=app_settings.SMSC_API_BASE_URL or None,
            api_key_encrypted=encrypt_secret(app_settings.SMSC_API_KEY) if app_settings.SMSC_API_KEY else None,
            timeout_seconds=app_settings.SMSC_API_TIMEOUT,
            session_expire_minutes=app_settings.SMSC_SESSION_EXPIRE_MINUTES,
            is_configured=bool(app_settings.SMSC_API_BASE_URL and app_settings.SMSC_API_KEY),
        )
        db.add(row)
        await db.flush()
    return row


async def is_enabled(db: AsyncSession) -> bool:
    row = await get_settings_row(db)
    return bool(row and row.enabled and row.is_configured)


async def _build_config(db: AsyncSession) -> SmscConfig:
    row = await get_settings_row(db)
    if row is None or not row.enabled or not row.is_configured or not row.api_base_url or not row.api_key_encrypted:
        raise SmscUnavailableError("SMSC integration is not configured")
    return SmscConfig(
        base_url=row.api_base_url,
        api_key=decrypt_secret(row.api_key_encrypted),
        auth_scheme=row.auth_scheme,
        timeout_seconds=row.timeout_seconds,
    )


async def get_packages(db: AsyncSession, *, conversation_id: uuid.UUID) -> list[dict] | None:
    """Platform-wide SMS package tiers for the public sales chatbot.
    Unlike every other call in this module, this isn't gated behind an
    authenticated SmscSession — the sales flow talks to anonymous
    prospects who haven't (and may never) authenticate at all. Returns
    None if the SMSC integration isn't enabled/configured, or the call
    fails — the caller falls back to a generic response rather than
    surfacing an error, same spirit as identify_from_widget_login_token."""
    if not await is_enabled(db):
        return None
    try:
        config = await _build_config(db)
        body = await smsc_client.get_packages(config)
    except SmscApiError as exc:
        await _log_call(
            db, conversation_id=conversation_id, smsc_user_id=None, endpoint="/packages",
            request_type="GET", response_status=None, success=False, error_message=str(exc),
        )
        return None

    await _log_call(
        db, conversation_id=conversation_id, smsc_user_id=None, endpoint="/packages",
        request_type="GET", response_status=200, success=True,
    )
    return body.get("packages") or []


async def get_services_public(db: AsyncSession, *, conversation_id: uuid.UUID) -> list[dict] | None:
    """Platform-wide product/service catalog, for the widget's Sales menu.
    Unlike every other call in this module (except get_packages/
    get_pricing_public above), this isn't gated behind an authenticated
    SmscSession — both anonymous prospects and logged-in dashboard users
    see the same catalog. Returns None if the SMSC integration isn't
    enabled/configured, or the call fails — the caller falls back to its
    own hardcoded menu rather than surfacing an error."""
    if not await is_enabled(db):
        return None
    try:
        config = await _build_config(db)
        body = await smsc_client.get_services(config)
    except SmscApiError as exc:
        await _log_call(
            db, conversation_id=conversation_id, smsc_user_id=None, endpoint="/services",
            request_type="GET", response_status=None, success=False, error_message=str(exc),
        )
        return None

    await _log_call(
        db, conversation_id=conversation_id, smsc_user_id=None, endpoint="/services",
        request_type="GET", response_status=200, success=True,
    )
    return body.get("services") or []


async def get_pricing_public(db: AsyncSession, *, conversation_id: uuid.UUID, service_type: str = "sms_mt") -> list[dict] | None:
    """Platform-wide per-country pricing for the public sales chatbot —
    the same data get_smsc_pricing exposes to authenticated sessions via
    call_tool, but reachable without one (mirrors get_packages above for
    the same reason: anonymous prospects have no SmscSession). Also
    doubles as the "which countries do you cover" answer — the country
    list in the response IS the coverage list. Returns None if the SMSC
    integration isn't enabled/configured, or the call fails."""
    if not await is_enabled(db):
        return None
    try:
        config = await _build_config(db)
        body = await smsc_client.get_pricing(config, service_type=service_type)
    except SmscApiError as exc:
        await _log_call(
            db, conversation_id=conversation_id, smsc_user_id=None, endpoint="/pricing",
            request_type="GET", response_status=None, success=False, error_message=str(exc),
        )
        return None

    await _log_call(
        db, conversation_id=conversation_id, smsc_user_id=None, endpoint="/pricing",
        request_type="GET", response_status=200, success=True,
    )
    return body.get("rates") or []


def _strip_sensitive(data: object) -> object:
    if isinstance(data, dict):
        return {k: _strip_sensitive(v) for k, v in data.items() if not _SENSITIVE_KEY_PATTERN.search(k)}
    if isinstance(data, list):
        return [_strip_sensitive(v) for v in data]
    return data


async def _log_call(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    smsc_user_id: str | None,
    endpoint: str,
    request_type: str,
    response_status: int | None,
    success: bool,
    error_message: str | None = None,
) -> None:
    db.add(
        SmscApiLog(
            conversation_id=conversation_id,
            smsc_user_id=smsc_user_id,
            endpoint=endpoint,
            request_type=request_type,
            response_status=response_status,
            success=success,
            error_message=(error_message or "")[:500] or None,
        )
    )
    await db.flush()


# --- Session lifecycle -------------------------------------------------


async def get_session(db: AsyncSession, conversation_id: uuid.UUID) -> SmscSession | None:
    result = await db.execute(select(SmscSession).where(SmscSession.conversation_id == conversation_id))
    session_row = result.scalar_one_or_none()
    if session_row is None:
        return None

    if (
        session_row.status == SmscSessionStatus.AUTHENTICATED
        and session_row.expires_at is not None
        and session_row.expires_at < datetime.now(timezone.utc)
    ):
        session_row.status = SmscSessionStatus.EXPIRED
        await db.flush()

    return session_row


async def start_pending(
    db: AsyncSession, *, conversation_id: uuid.UUID, visitor_id: uuid.UUID, pending_question: str
) -> SmscSession:
    existing = await get_session(db, conversation_id)
    if existing is not None and existing.status == SmscSessionStatus.PENDING:
        existing.pending_question = pending_question
        await db.flush()
        return existing
    if existing is not None:
        # Re-asking after EXPIRED/TERMINATED: reuse the row rather than
        # violating the one-session-per-conversation unique constraint.
        existing.status = SmscSessionStatus.PENDING
        existing.pending_question = pending_question
        existing.smsc_user_id = None
        existing.username = None
        existing.role = None
        existing.authenticated_at = None
        existing.expires_at = None
        await db.flush()
        return existing

    session_row = SmscSession(
        conversation_id=conversation_id,
        visitor_id=visitor_id,
        session_token=secrets.token_urlsafe(32),
        status=SmscSessionStatus.PENDING,
        pending_question=pending_question,
    )
    db.add(session_row)
    await db.flush()
    return session_row


async def resolve_widget_login_token(
    db: AsyncSession, *, conversation_id: uuid.UUID, login_token: str
) -> tuple[str, str, str | None] | None:
    """Exchanges the Laravel dashboard's short-lived, single-use widget
    login token for the identity it carries (smsc_user_id, username, role),
    without binding it to any conversation yet — see
    authenticate_session_identity for that. Split out from the old
    identify_from_widget_login_token (still below, now a thin wrapper of
    both) so a caller can learn *who* a login_token belongs to before
    deciding *which* conversation it should apply to. That distinction
    matters because the token is single-use (consumed here via the
    Laravel side's Cache::pull), so identity must be resolved before, not
    after, that decision — see app.api.routes.widget.create_session, which
    uses it to detect a stale/reused session_token now representing a
    different logged-in person than before, and start a fresh conversation
    instead of silently continuing to answer as the wrong account.
    Returns None on any failure (missing/expired/already-used token,
    integration disabled, etc.) — callers must fall back to the normal
    ask-for-username flow silently, without surfacing an error."""
    if not await is_enabled(db):
        return None

    try:
        config = await _build_config(db)
    except SmscUnavailableError:
        return None

    try:
        body = await smsc_client.exchange_widget_token(config, login_token)
    except SmscApiError as exc:
        await _log_call(
            db, conversation_id=conversation_id, smsc_user_id=None, endpoint="/auth/exchange-widget-token",
            request_type="POST", response_status=None, success=False, error_message=str(exc),
        )
        return None

    success = bool(body.get("success"))
    await _log_call(
        db, conversation_id=conversation_id, smsc_user_id=None, endpoint="/auth/exchange-widget-token",
        request_type="POST", response_status=200, success=success,
    )
    if not success:
        return None

    user = body.get("user") or {}
    smsc_user_id = str(user.get("id")) if user.get("id") is not None else None
    username = user.get("username")
    if not smsc_user_id or not username:
        return None

    role = str(user.get("role")) if user.get("role") else None
    return smsc_user_id, str(username), role


async def authenticate_session_identity(
    db: AsyncSession, *, conversation_id: uuid.UUID, visitor_id: uuid.UUID,
    smsc_user_id: str, username: str, role: str | None,
) -> SmscSession:
    """Binds an already-resolved identity (see resolve_widget_login_token)
    to conversation_id's SmscSession row, overwriting whatever identity
    (if any — including a different one) was there before."""
    settings_row = await get_settings_row(db)
    expire_minutes = settings_row.session_expire_minutes if settings_row else 30

    session_row = await start_pending(
        db, conversation_id=conversation_id, visitor_id=visitor_id, pending_question=""
    )
    session_row.smsc_user_id = smsc_user_id
    session_row.username = username
    session_row.role = role
    session_row.status = SmscSessionStatus.AUTHENTICATED
    session_row.authenticated_at = datetime.now(timezone.utc)
    session_row.expires_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    session_row.failed_attempts = 0
    session_row.pending_question = None
    await db.flush()

    return session_row


async def identify_from_widget_login_token(
    db: AsyncSession, *, conversation_id: uuid.UUID, visitor_id: uuid.UUID, login_token: str
) -> tuple[str, str | None] | None:
    """Convenience wrapper for the common case (a brand-new conversation,
    where there's no existing identity to reconcile against): resolves the
    login_token and immediately binds it to conversation_id. Returns
    (username, role) on success, None on any failure — see
    resolve_widget_login_token for what "failure" covers."""
    resolved = await resolve_widget_login_token(db, conversation_id=conversation_id, login_token=login_token)
    if resolved is None:
        return None
    smsc_user_id, username, role = resolved
    session_row = await authenticate_session_identity(
        db, conversation_id=conversation_id, visitor_id=visitor_id,
        smsc_user_id=smsc_user_id, username=username, role=role,
    )
    return session_row.username, session_row.role


async def terminate_session(db: AsyncSession, session_row: SmscSession) -> None:
    session_row.status = SmscSessionStatus.TERMINATED
    session_row.smsc_user_id = None
    session_row.username = None
    session_row.role = None
    session_row.expires_at = None
    await db.flush()


# --- Tool dispatch (called by the AI tool-calling loop) -----------------


class SmscToolError(Exception):
    """Raised for the AI orchestrator to translate into one of the fixed,
    honest failure messages instead of letting the model guess."""

    def __init__(self, user_message: str) -> None:
        self.user_message = user_message
        super().__init__(user_message)


async def call_tool(
    db: AsyncSession, *, session_row: SmscSession, conversation_id: uuid.UUID, tool_name: str, arguments: dict
) -> dict:
    if tool_name not in _TOOL_ENDPOINTS:
        raise SmscToolError("I can't perform that action.")
    if session_row.status != SmscSessionStatus.AUTHENTICATED or not session_row.smsc_user_id:
        raise SmscToolError("Please verify your SMSC account first.")

    endpoint_template, method, required_role = _TOOL_ENDPOINTS[tool_name]
    if required_role is not None and session_row.role != required_role:
        # Not just hidden from the tool list offered to the model — enforced
        # here too, in case the model calls it anyway.
        raise SmscToolError("You don't have permission to access this information. Please contact support.")
    if session_row.role == "support" and tool_name in _ACCOUNT_SCOPED_TOOLS:
        raise SmscToolError(
            "A support login has no SMSC account of its own. Please give me a message id, username, or "
            "account you'd like me to look into instead."
        )

    message_id = arguments.get("message_id")
    endpoint = endpoint_template.format(user=session_row.smsc_user_id, message_id=message_id or "")

    try:
        config = await _build_config(db)
    except SmscUnavailableError:
        await _log_call(
            db, conversation_id=conversation_id, smsc_user_id=session_row.smsc_user_id, endpoint=endpoint,
            request_type=method, response_status=None, success=False, error_message="not configured",
        )
        raise SmscToolError(
            "I'm unable to retrieve your SMSC account information right now. Please try again later or contact support."
        )

    date_from = arguments.get("date_from")
    date_to = arguments.get("date_to")

    try:
        if tool_name == "get_smsc_balance":
            result = await smsc_client.get_balance(config, session_row.smsc_user_id)
        elif tool_name == "get_smsc_traffic":
            result = await smsc_client.get_traffic(config, session_row.smsc_user_id, date_from=date_from, date_to=date_to)
        elif tool_name == "get_smsc_delivery_stats":
            result = await smsc_client.get_delivery_stats(
                config, session_row.smsc_user_id, date_from=date_from, date_to=date_to
            )
        elif tool_name == "get_smsc_traffic_breakdown":
            by = arguments.get("by") or "country"
            result = await smsc_client.get_traffic_breakdown(
                config, session_row.smsc_user_id, by=by, date_from=date_from, date_to=date_to
            )
        elif tool_name == "get_smsc_failure_analysis":
            result = await smsc_client.get_failure_analysis(
                config, session_row.smsc_user_id, date_from=date_from, date_to=date_to
            )
        elif tool_name == "get_smsc_connections":
            result = await smsc_client.get_connections(config, session_row.smsc_user_id)
        elif tool_name == "get_smsc_sender_ids":
            result = await smsc_client.get_sender_ids(config, session_row.smsc_user_id)
        elif tool_name == "get_smsc_account_status":
            result = await smsc_client.get_account_status(config, session_row.smsc_user_id)
        elif tool_name == "get_smsc_smpp_status":
            result = await smsc_client.get_smpp_status(config, session_row.smsc_user_id)
        elif tool_name == "get_smsc_http_api_status":
            result = await smsc_client.get_http_api_status(config, session_row.smsc_user_id)
        elif tool_name == "get_smsc_hlr_status":
            result = await smsc_client.get_hlr_status(config, session_row.smsc_user_id)
        elif tool_name == "get_smsc_dlr_status":
            result = await smsc_client.get_dlr_status(config, session_row.smsc_user_id)
        elif tool_name == "get_smsc_pricing":
            service_type = arguments.get("service_type") or "sms_mt"
            result = await smsc_client.get_pricing(config, service_type=service_type)
        elif tool_name == "get_smsc_own_message_status":
            if not message_id:
                raise SmscToolError("Please provide the message id you'd like me to look up.")
            result = await smsc_client.get_own_message_status(config, session_row.smsc_user_id, str(message_id))
        else:
            if not message_id:
                raise SmscToolError("Please provide the message id you'd like me to look up.")
            result = await smsc_client.get_message_status(config, str(message_id))
    except SmscUnavailableError as exc:
        await _log_call(
            db, conversation_id=conversation_id, smsc_user_id=session_row.smsc_user_id, endpoint=endpoint,
            request_type=method, response_status=None, success=False, error_message=str(exc),
        )
        raise SmscToolError(
            "I'm unable to retrieve your SMSC account information right now. Please try again later or contact support."
        )
    except SmscNotFoundError as exc:
        await _log_call(
            db, conversation_id=conversation_id, smsc_user_id=session_row.smsc_user_id, endpoint=endpoint,
            request_type=method, response_status=404, success=False, error_message=str(exc),
        )
        raise SmscToolError(
            "I couldn't find a message with that id."
            if tool_name in ("get_smsc_message_status", "get_smsc_own_message_status")
            else "I couldn't find that information for your account."
        )
    except SmscApiError as exc:
        await _log_call(
            db, conversation_id=conversation_id, smsc_user_id=session_row.smsc_user_id, endpoint=endpoint,
            request_type=method, response_status=None, success=False, error_message=str(exc),
        )
        raise SmscToolError("You don't have permission to access this information. Please contact support.")

    await _log_call(
        db, conversation_id=conversation_id, smsc_user_id=session_row.smsc_user_id, endpoint=endpoint,
        request_type=method, response_status=200, success=True,
    )
    return _strip_sensitive(result)
