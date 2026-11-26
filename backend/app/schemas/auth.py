"""
FinSight AI — Auth & Profile Pydantic Schemas
"""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


def _strong_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    return v


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _strong_password(v)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    is_verified: bool
    role: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    default_currency: str = "USD"
    timezone: str = "UTC"
    created_at: Optional[datetime] = None


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = Field(None, max_length=2000)
    default_currency: Optional[str] = Field(None, pattern="^(USD|INR|EUR|GBP)$")
    timezone: Optional[str] = Field(None, max_length=100)


class PreferencesResponse(BaseModel):
    theme: str = "dark"
    default_market: str = "US"
    dashboard_layout: Optional[dict] = None
    alert_channels: Optional[dict] = None

    model_config = {"from_attributes": True}


class UpdatePreferencesRequest(BaseModel):
    theme: Optional[str] = Field(None, pattern="^(dark|light|system)$")
    default_market: Optional[str] = Field(None, pattern="^(US|IN)$")
    dashboard_layout: Optional[dict] = None
    alert_channels: Optional[dict] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _strong_password(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _strong_password(v)
