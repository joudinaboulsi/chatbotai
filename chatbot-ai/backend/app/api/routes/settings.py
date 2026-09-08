from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.db import get_db
from app.core.smsc_client import SmscApiError, SmscAuthError, SmscConfig, SmscUnavailableError, validate_user
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.settings import (
    EmailSettingsOut,
    EmailSettingsUpdate,
    SMSCSettingsOut,
    SMSCSettingsUpdate,
    SMSCTestResponse,
    TestEmailRequest,
)
from app.services import email_service, smsc_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/settings/email", tags=["settings"])
smsc_router = APIRouter(prefix="/settings/smsc", tags=["settings"])

_manage_roles = require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)


@router.get("", response_model=EmailSettingsOut)
async def get_email_settings(
    user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> EmailSettingsOut:
    row = await email_service.get_or_create_settings_row(db)
    await db.commit()
    return EmailSettingsOut.model_validate(row, from_attributes=True)


@router.put("", response_model=EmailSettingsOut)
async def update_email_settings(
    body: EmailSettingsUpdate,
    request: Request,
    user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> EmailSettingsOut:
    row = await email_service.get_or_create_settings_row(db)
    data = body.model_dump(exclude_unset=True)

    if "smtp_password" in data:
        password = data.pop("smtp_password")
        row.smtp_password_encrypted = encrypt_secret(password) if password else None
    for field, value in data.items():
        setattr(row, field, value)

    row.is_configured = bool(row.smtp_host and row.from_email and row.support_email)
    await db.flush()
    await log_action(
        db, user_id=user.id, action="settings_changed", resource_type="email_settings", resource_id=row.id,
        ip_address=request.client.host if request.client else None,
        details={k: v for k, v in data.items() if k != "smtp_password"},
    )
    await db.commit()
    return EmailSettingsOut.model_validate(row, from_attributes=True)


@router.post("/test", status_code=status.HTTP_204_NO_CONTENT)
async def test_email_configuration(
    body: TestEmailRequest, user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> None:
    try:
        sent = await email_service.send_email(
            db,
            to_email=body.to_email,
            subject="Test Email - AI Chatbot Platform",
            body_text="This is a test email confirming your SMTP configuration works correctly.",
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Failed to send test email: {exc}") from exc

    if not sent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email is not fully configured yet")


@smsc_router.get("", response_model=SMSCSettingsOut)
async def get_smsc_settings(
    user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> SMSCSettingsOut:
    row = await smsc_service.get_or_create_settings_row(db)
    await db.commit()
    return SMSCSettingsOut.model_validate(row, from_attributes=True)


@smsc_router.put("", response_model=SMSCSettingsOut)
async def update_smsc_settings(
    body: SMSCSettingsUpdate,
    request: Request,
    user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SMSCSettingsOut:
    row = await smsc_service.get_or_create_settings_row(db)
    data = body.model_dump(exclude_unset=True)

    if "api_key" in data:
        api_key = data.pop("api_key")
        row.api_key_encrypted = encrypt_secret(api_key) if api_key else None
    for field, value in data.items():
        setattr(row, field, value)

    row.is_configured = bool(row.api_base_url and row.api_key_encrypted)
    await db.flush()
    await log_action(
        db,
        user_id=user.id,
        action="settings_changed",
        resource_type="smsc_settings",
        resource_id=row.id,
        ip_address=request.client.host if request.client else None,
        details={k: v for k, v in data.items() if k != "api_key"},
    )
    await db.commit()
    return SMSCSettingsOut.model_validate(row, from_attributes=True)


@smsc_router.post("/test", response_model=SMSCTestResponse)
async def test_smsc_connection(user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)) -> SMSCTestResponse:
    row = await smsc_service.get_settings_row(db)
    if row is None or not row.is_configured or not row.api_base_url or not row.api_key_encrypted:
        return SMSCTestResponse(connected=False, detail="SMSC integration is not fully configured yet.")

    config = SmscConfig(
        base_url=row.api_base_url,
        api_key=decrypt_secret(row.api_key_encrypted),
        auth_scheme=row.auth_scheme,
        timeout_seconds=row.timeout_seconds,
    )
    try:
        # A round trip to /auth/validate-user with a throwaway username is
        # enough to confirm the base URL and API key work — a "not found"
        # response still proves the API is reachable and authenticated.
        await validate_user(config, "__connection_test__")
        return SMSCTestResponse(connected=True, detail="Successfully connected to the SMSC API.")
    except SmscAuthError:
        return SMSCTestResponse(connected=False, detail="The SMSC API rejected the configured API key.")
    except SmscUnavailableError as exc:
        return SMSCTestResponse(connected=False, detail=f"Could not reach the SMSC API: {exc}")
    except SmscApiError as exc:
        return SMSCTestResponse(connected=True, detail=f"Reached the SMSC API (unexpected response: {exc}).")
