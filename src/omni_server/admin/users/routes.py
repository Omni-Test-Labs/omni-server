"""User management API routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import NotificationDB, UserDB
from ...auth.routes import get_current_user
from ...config import Settings
from .models import (
    AuditLogListResponse,
    AuditLogResponse,
    NotificationListResponse,
    NotificationMarkAllReadRequest,
    NotificationResponse,
    NotificationUpdateRequest,
    UserCreateAdminRequest,
    UserListResponse,
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
    UserUpdateRequest,
)
from .service import UserService
from ...auth.service import AuthService

router = APIRouter(prefix="/api/users", tags=["users"])
settings = Settings()
auth_service = AuthService(settings)
user_service = UserService(auth_service)


@router.get("", response_model=UserListResponse, status_code=status.HTTP_200_OK)
def list_users(
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> UserListResponse:
    """List all users (paginated)."""
    return user_service.list_users(db, page, page_size)


@router.get("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_user(
    user_id: int,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Get user by ID."""
    return user_service.get_user(db, user_id)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreateAdminRequest,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Create a new user (admin only)."""
    return user_service.create_user(db, user_data, current_user.id)


@router.patch("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_user(
    user_id: int,
    update_data: UserUpdateRequest,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Update user."""
    return user_service.update_user(db, user_id, update_data, current_user.id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete user."""
    user_service.delete_user(db, user_id, current_user.id)


# Settings endpoints


@router.get(
    "/{user_id}/settings", response_model=UserSettingsResponse, status_code=status.HTTP_200_OK
)
def get_user_settings(
    user_id: int,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserSettingsResponse:
    """Get user settings."""
    return user_service.get_user_settings(db, user_id)


@router.patch(
    "/{user_id}/settings", response_model=UserSettingsResponse, status_code=status.HTTP_200_OK
)
def update_user_settings(
    user_id: int,
    update_data: UserSettingsUpdateRequest,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserSettingsResponse:
    """Update user settings."""
    return user_service.update_user_settings(db, user_id, update_data, current_user.id)


# Notifications endpoints


@router.get(
    "/{user_id}/notifications",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
)
def list_notifications(
    user_id: int,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
) -> NotificationListResponse:
    """List user notifications."""
    return user_service.list_notifications(db, user_id, page, page_size, unread_only)


@router.get(
    "/{user_id}/notifications/{notification_id}",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
)
def get_notification(
    user_id: int,
    notification_id: int,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationResponse:
    """Get notification by ID."""
    notification = (
        db.query(NotificationDB)
        .filter(NotificationDB.id == notification_id, NotificationDB.user_id == user_id)
        .first()
    )
    if not notification:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        read=notification.read,
        link_url=notification.link_url,
        metadata=notification.meta_data,
        created_at=notification.created_at,
    )


@router.patch(
    "/{user_id}/notifications/{notification_id}",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
)
def update_notification(
    user_id: int,
    notification_id: int,
    update_data: NotificationUpdateRequest,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationResponse:
    """Update notification (mark as read/unread)."""
    return user_service.update_notification(db, user_id, notification_id, update_data)


@router.post("/{user_id}/notifications/mark-all-read", status_code=status.HTTP_200_OK)
def mark_all_notifications_read(
    user_id: int,
    request_data: NotificationMarkAllReadRequest,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Mark all notifications as read."""
    count = user_service.mark_all_notifications_read(db, user_id)
    return {"count": count, "message": f"Marked {count} notifications as read"}


# Audit logs endpoints

audit_router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"])


@audit_router.get("", response_model=AuditLogListResponse, status_code=status.HTTP_200_OK)
def list_audit_logs(
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None),
) -> AuditLogListResponse:
    """List audit logs (paginated)."""
    return user_service.list_audit_logs(db, page, page_size, user_id)
