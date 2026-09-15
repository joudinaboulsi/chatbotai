import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole, UserStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole
    status: UserStatus

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
