"""Pydantic schemas for authentication and authorization."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ==================== Request Schemas ====================


class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="Password")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v.isalnum() and "_" not in v:
            raise ValueError("Username must be alphanumeric with optional underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)

        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one digit"
            )
        return v


class UserLoginRequest(BaseModel):
    """Request schema for user login."""

    identifier: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class TokenRefreshRequest(BaseModel):
    """Request schema for token refresh."""

    refresh_token: str = Field(..., description="JWT refresh token")


class UserUpdateRequest(BaseModel):
    """Request schema for updating user settings."""

    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None
    preferences: Optional[dict[str, Any]] = None
    theme: Optional[str] = Field(None, pattern="^(light|dark|auto)$")
    language: Optional[str] = Field(None, min_length=2, max_length=10)
    timezone: Optional[str] = None
    notification_email: Optional[bool] = None
    notification_web: Optional[bool] = None


class PasswordChangeRequest(BaseModel):
    """Request schema for changing password."""

    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)

        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one digit"
            )
        return v


# ==================== Response Schemas ====================


class UserResponse(BaseModel):
    """Response schema for user data."""

    id: int
    username: str
    email: str
    avatar_url: Optional[str] = None
    role: str
    role_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserSettingsResponse(BaseModel):
    """Response schema for user settings."""

    preferences: dict[str, Any]
    theme: str
    language: str
    notification_email: bool
    notification_web: bool
    timezone: str


class UserDetailResponse(UserResponse):
    """Detailed user response with settings."""

    settings: UserSettingsResponse


class TokenResponse(BaseModel):
    """Response schema for authentication tokens."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_in: int


class OAuthCallbackRequest(BaseModel):
    """Request schema for OAuth callback."""

    code: str = Field(..., description="OAuth authorization code")
    state: Optional[str] = Field(None, description="OAuth state parameter for CSRF protection")
