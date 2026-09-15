"""Thin HTTP client for the external SMSC API. This is the only module in
the codebase allowed to know the SMSC API's base URL/key — everything else
(AI tool dispatch, conversation flow, admin settings) goes through
app.services.smsc_service instead of importing this directly, so the
credential/URL never has to travel further than necessary.

The chatbot NEVER connects to the SMSC MySQL database. Every one of these
calls is a plain HTTPS request to the documented SMSC API endpoints below.
Expected endpoint contract (adjust paths here if the real SMSC API differs):

    POST /auth/validate-user            {"username"} -> {user}
    POST /auth/exchange-widget-token    {"token"} -> {user}
    GET  /users/{user}/balance
    GET  /users/{user}/traffic          ?date_from=&date_to=
    GET  /users/{user}/delivery-stats   ?date_from=&date_to=
    GET  /users/{user}/connections
    GET  /users/{user}/status
    GET  /users/{user}/smpp-status
    GET  /users/{user}/http-api-status
    GET  /users/{user}/hlr-status
    GET  /users/{user}/dlr-status
    GET  /users/{user}/messages/{message_id}   user-scoped: only that user's own messages
    GET  /messages/{message_id}        support-only diagnostic lookup, not user-scoped
    GET  /pricing                      ?service_type=sms_mt|sms_mo|hlr — platform-wide, not user-scoped
    GET  /packages                     platform-wide SMS package tiers, not user-scoped
"""

import logging

import httpx

from app.models.enums import SmscAuthScheme

logger = logging.getLogger("app.smsc_client")


class SmscApiError(Exception):
    """Base class for all SMSC API failures."""


class SmscUnavailableError(SmscApiError):
    """Network error, timeout, or 5xx — the API could not be reached."""


class SmscAuthError(SmscApiError):
    """401/403 — our own API key was rejected, or the caller isn't
    authorized for this resource."""


class SmscNotFoundError(SmscApiError):
    """404 — e.g. no such SMSC user."""


class SmscConfig:
    def __init__(self, *, base_url: str, api_key: str, auth_scheme: SmscAuthScheme, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.auth_scheme = auth_scheme
        self.timeout_seconds = timeout_seconds

def _auth_headers(config: SmscConfig) -> dict[str, str]:
    if config.auth_scheme == SmscAuthScheme.BEARER:
        return {"Authorization": f"Bearer {config.api_key}"}
    return {"X-API-Key": config.api_key}


async def _request(config: SmscConfig, method: str, path: str, **kwargs) -> tuple[int, dict]:
    url = f"{config.base_url}{path}"
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds), headers=_auth_headers(config)
        ) as client:
            response = await client.request(method, url, **kwargs)
    except httpx.RequestError as exc:
        raise SmscUnavailableError(f"Could not reach SMSC API: {exc}") from exc

    if response.status_code in (401, 403):
        raise SmscAuthError(f"SMSC API rejected the request ({response.status_code})")
    if response.status_code == 404:
        raise SmscNotFoundError("Not found")
    if response.status_code >= 500:
        raise SmscUnavailableError(f"SMSC API error ({response.status_code})")
    if response.status_code >= 400:
        raise SmscApiError(f"SMSC API returned {response.status_code}")

    try:
        body = response.json()
    except ValueError as exc:
        raise SmscApiError("SMSC API returned a non-JSON response") from exc

    return response.status_code, body if isinstance(body, dict) else {}


async def validate_user(config: SmscConfig, username: str) -> dict:
    _, body = await _request(config, "POST", "/auth/validate-user", json={"username": username})
    return body


async def exchange_widget_token(config: SmscConfig, login_token: str) -> dict:
    _, body = await _request(config, "POST", "/auth/exchange-widget-token", json={"token": login_token})
    return body


async def get_balance(config: SmscConfig, smsc_user_id: str) -> dict:
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/balance")
    return body


async def get_traffic(config: SmscConfig, smsc_user_id: str, *, date_from: str | None, date_to: str | None) -> dict:
    params = {k: v for k, v in {"date_from": date_from, "date_to": date_to}.items() if v}
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/traffic", params=params)
    return body


async def get_delivery_stats(
    config: SmscConfig, smsc_user_id: str, *, date_from: str | None, date_to: str | None
) -> dict:
    params = {k: v for k, v in {"date_from": date_from, "date_to": date_to}.items() if v}
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/delivery-stats", params=params)
    return body


async def get_traffic_breakdown(
    config: SmscConfig, smsc_user_id: str, *, by: str, date_from: str | None, date_to: str | None
) -> dict:
    params = {k: v for k, v in {"by": by, "date_from": date_from, "date_to": date_to}.items() if v}
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/traffic/breakdown", params=params)
    return body


async def get_failure_analysis(
    config: SmscConfig, smsc_user_id: str, *, date_from: str | None, date_to: str | None
) -> dict:
    params = {k: v for k, v in {"date_from": date_from, "date_to": date_to}.items() if v}
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/failures", params=params)
    return body


async def get_connections(config: SmscConfig, smsc_user_id: str) -> dict:
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/connections")
    return body


async def get_sender_ids(config: SmscConfig, smsc_user_id: str) -> dict:
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/sender-ids")
    return body


async def get_account_status(config: SmscConfig, smsc_user_id: str) -> dict:
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/status")
    return body


async def get_smpp_status(config: SmscConfig, smsc_user_id: str) -> dict:
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/smpp-status")
    return body


async def get_http_api_status(config: SmscConfig, smsc_user_id: str) -> dict:
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/http-api-status")
    return body


async def get_hlr_status(config: SmscConfig, smsc_user_id: str) -> dict:
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/hlr-status")
    return body


async def get_dlr_status(config: SmscConfig, smsc_user_id: str) -> dict:
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/dlr-status")
    return body


async def get_message_status(config: SmscConfig, message_id: str) -> dict:
    """Support-only: looks up any user's message by id/uuid. Not scoped to
    a smsc_user_id — see app.services.smsc_service.call_tool for the
    role check that gates this before it's ever reached."""
    _, body = await _request(config, "GET", f"/messages/{message_id}")
    return body


async def get_own_message_status(config: SmscConfig, smsc_user_id: str, message_id: str) -> dict:
    """User-scoped: looks up a message by id/uuid, but only if it belongs
    to smsc_user_id — the API 404s otherwise, so this can safely be
    offered to a regular customer's own session without letting them see
    another customer's message (unlike get_message_status above)."""
    _, body = await _request(config, "GET", f"/users/{smsc_user_id}/messages/{message_id}")
    return body


async def get_pricing(config: SmscConfig, *, service_type: str) -> dict:
    """Platform-wide per-country pricing (same for every account in this
    demo). Not user-scoped — lets the AI compute affordability itself
    instead of asking the visitor to look pricing up somewhere."""
    _, body = await _request(config, "GET", "/pricing", params={"service_type": service_type})
    return body


async def get_packages(config: SmscConfig) -> dict:
    """Platform-wide SMS package tiers (same for every prospect). Not
    user-scoped and not gated behind an SmscSession — the public sales
    chatbot talks to anonymous prospects who haven't authenticated at
    all, unlike every other call in this module."""
    _, body = await _request(config, "GET", "/packages")
    return body


async def get_services(config: SmscConfig) -> dict:
    """Platform-wide product/service catalog (same for every prospect).
    Not user-scoped and not gated behind an SmscSession, same reasoning
    as get_packages above — backs the Sales menu so it lists every real
    product instead of a hardcoded subset."""
    _, body = await _request(config, "GET", "/services")
    return body
