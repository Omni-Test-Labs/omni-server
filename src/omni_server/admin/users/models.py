"""Pydantic schemas for user management APIs."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, EmailStr


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


class UserListResponse(BaseModel):
    """Paginated list response for users."""

    users: list[UserResponse]
    total: int
    page: int
    page_size: int


class UserUpdateRequest(BaseModel):
    """Request schema for updating user (admin only)."""

    username: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserSettingsResponse(BaseModel):
    """Response schema for user settings."""

    id: int
    user_id: int
    preferences: dict[str, Any]
    theme: str
    language: str
    notification_email: bool
    notification_web: bool
    timezone: str
    created_at: datetime
    updated_at: datetime


class UserSettingsUpdateRequest(BaseModel):
    """Request schema for updating user settings."""

    preferences: Optional[dict[str, Any]] = None
    theme: Optional[str] = Field(None, pattern="^(light|dark|auto)$")
    language: Optional[str] = Field(None, min_length=2, max_length=10)
    timezone: Optional[str] = None
    notification_email: Optional[bool] = None
    notification_web: Optional[bool] = None


class NotificationResponse(BaseModel):
    """Response schema for notifications."""

    id: int
    user_id: int
    type: str
    title: str
    message: str
    read: bool
    link_url: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated list response for notifications."""

    notifications: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class NotificationUpdateRequest(BaseModel):
    """Request schema for updating notification."""

    read: bool = True


class NotificationMarkAllReadRequest(BaseModel):
    """Request schema to mark all notifications as read."""

    mark_all_as_read: bool = True


class AuditLogResponse(BaseModel):
    """Response schema for audit logs."""

    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list response for audit logs."""

    audit_logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class UserCreateAdminRequest(BaseModel):
    """Request schema for admin to create a user."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    role_id: int
    avatar_url: Optional[str] = None
