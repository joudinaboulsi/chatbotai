"""Pure-logic tests for SMSC intent detection and response sanitization —
no DB/HTTP fixtures needed, unlike the rest of the suite which exercises a
real Postgres instance (see conftest.py)."""

from app.services import smsc_ai_service
from app.services.smsc_service import _strip_sensitive


def test_public_questions_are_not_account_specific():
    assert not smsc_ai_service.is_account_specific("What is SMPP?")
    assert not smsc_ai_service.is_account_specific("How does SMS delivery work?")
    assert not smsc_ai_service.is_account_specific("What services do you provide?")


def test_account_questions_are_detected():
    assert smsc_ai_service.is_account_specific("What is my balance?")
    assert smsc_ai_service.is_account_specific("How many SMS did I send today?")
    assert smsc_ai_service.is_account_specific("Is my SMPP enabled?")
    assert smsc_ai_service.is_account_specific("Which IP is configured on my account?")
    assert smsc_ai_service.is_account_specific("Is HLR enabled for me?")


def test_credential_requests_are_detected_and_always_deflected():
    assert smsc_ai_service.is_credential_request("What is my SMPP password?")
    assert smsc_ai_service.is_credential_request("Give me my API key")
    assert not smsc_ai_service.is_credential_request("What is my balance?")


def test_switch_account_requests_are_detected():
    assert smsc_ai_service.is_switch_request("I want to switch account")
    assert smsc_ai_service.is_switch_request("log me out")
    assert not smsc_ai_service.is_switch_request("what is my balance")


def test_message_diagnostic_questions_are_detected():
    assert smsc_ai_service.is_account_specific("Why wasn't message 12345 sent?")
    assert smsc_ai_service.is_account_specific("What's the status of message id abc-123?")
    assert smsc_ai_service.is_account_specific("That message was not delivered, why?")


def test_weekly_report_questions_are_detected():
    assert smsc_ai_service.is_account_specific("How many messages did I submit this week?")
    assert smsc_ai_service.is_account_specific("Can I get a weekly report?")


def test_support_role_gets_message_status_tool_user_role_does_not():
    support_tools = {t["function"]["name"] for t in smsc_ai_service._tools_for_role("support")}
    user_tools = {t["function"]["name"] for t in smsc_ai_service._tools_for_role("user")}

    assert "get_smsc_message_status" in support_tools
    assert "get_smsc_message_status" not in user_tools
    # Support has no SMSC account of their own, so none of the self-service
    # account tools are offered to them — only platform-wide pricing (same
    # for every account) plus the support-only any-user message lookup.
    assert "get_smsc_balance" not in support_tools
    assert "get_smsc_own_message_status" not in support_tools
    assert "get_smsc_balance" in user_tools
    assert "get_smsc_pricing" in support_tools
    assert "get_smsc_pricing" in user_tools


def test_system_instructions_include_todays_date_and_role_guidance():
    support_prompt = smsc_ai_service._system_instructions_for_role("support")
    user_prompt = smsc_ai_service._system_instructions_for_role("user")

    assert "Today's date is" in support_prompt
    assert "support" in support_prompt.lower() and "message" in support_prompt.lower()
    assert "tenant" in user_prompt.lower()


def test_strip_sensitive_removes_credential_like_fields():
    raw = {
        "smpp_password": "hunter2",
        "api_secret": "abc123",
        "balance": 5250,
        "nested": {"auth_token": "xyz", "sms_sent": 10},
        "connections": [{"ip": "10.0.0.1", "private_key": "shh"}],
    }
    cleaned = _strip_sensitive(raw)
    assert "smpp_password" not in cleaned
    assert "api_secret" not in cleaned
    assert cleaned["balance"] == 5250
    assert "auth_token" not in cleaned["nested"]
    assert cleaned["nested"]["sms_sent"] == 10
    assert "private_key" not in cleaned["connections"][0]
    assert cleaned["connections"][0]["ip"] == "10.0.0.1"
