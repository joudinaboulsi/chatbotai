from pydantic import BaseModel, EmailStr

from app.models.enums import SmscAuthScheme, SmtpEncryption


class EmailSettingsOut(BaseModel):
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    encryption: SmtpEncryption
    from_name: str | None
    from_email: str | None
    support_email: str | None
    is_configured: bool
    # smtp_password is intentionally never included in any response.


class EmailSettingsUpdate(BaseModel):
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    encryption: SmtpEncryption | None = None
    from_name: str | None = None
    from_email: EmailStr | None = None
    support_email: EmailStr | None = None


class TestEmailRequest(BaseModel):
    to_email: EmailStr


class SMSCSettingsOut(BaseModel):
    enabled: bool
    api_base_url: str | None
    auth_scheme: SmscAuthScheme
    timeout_seconds: int
    session_expire_minutes: int
    is_configured: bool
    # api_key is intentionally never included in any response.


class SMSCSettingsUpdate(BaseModel):
    enabled: bool | None = None
    api_base_url: str | None = None
    api_key: str | None = None
    auth_scheme: SmscAuthScheme | None = None
    timeout_seconds: int | None = None
    session_expire_minutes: int | None = None


class SMSCTestResponse(BaseModel):
    connected: bool
    detail: str
