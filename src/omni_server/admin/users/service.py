"""User management service."""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...models import AuditLogDB, NotificationDB, RoleDB, UserDB, UserSettingsDB
from ...auth.service import AuthService
from .models import (
    AuditLogListResponse,
    AuditLogResponse,
    NotificationListResponse,
    NotificationResponse,
    NotificationUpdateRequest,
    UserCreateAdminRequest,
    UserListResponse,
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
    UserUpdateRequest,
)


class UserService:
    """Service for user management operations."""

    def __init__(self, auth_service: AuthService):
        """Initialize user service."""
        self.auth_service = auth_service

    def create_audit_log(
        self,
        db: Session,
        user_id: int,
        action: str,
        entity_type: str,
        entity_id: Optional[str],
        details: dict,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """Create an audit log entry."""
        audit_log = AuditLogDB(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow(),
        )
        db.add(audit_log)
        db.commit()

    # User Management

    def list_users(self, db: Session, page: int = 1, page_size: int = 20) -> UserListResponse:
        """List all users with pagination."""
        total = db.query(UserDB).count()
        skip = (page - 1) * page_size
        users = db.query(UserDB).offset(skip).limit(page_size).all()

        user_responses = []
        for user in users:
            role = db.query(RoleDB).filter(RoleDB.id == user.role_id).first()
            user_responses.append(
                UserResponse(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    avatar_url=user.avatar_url,
                    role=role.name if role else "unknown",
                    role_id=user.role_id,
                    is_active=user.is_active,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
            )

        return UserListResponse(users=user_responses, total=total, page=page, page_size=page_size)

    def get_user(self, db: Session, user_id: int) -> UserResponse:
        """Get user by ID."""
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        role = db.query(RoleDB).filter(RoleDB.id == user.role_id).first()
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            role=role.name if role else "unknown",
            role_id=user.role_id,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def create_user(
        self, db: Session, user_data: UserCreateAdminRequest, admin_user_id: int
    ) -> UserResponse:
        """Create a new user (admin only)."""
        # Check if username exists
        existing_user = db.query(UserDB).filter(UserDB.username == user_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
            )

        # Check if email exists
        existing_email = db.query(UserDB).filter(UserDB.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            )

        # Validate role
        role = db.query(RoleDB).filter(RoleDB.id == user_data.role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found")

        # Create user
        hashed_password = self.auth_service.hash_password(user_data.password)
        user = UserDB(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            avatar_url=user_data.avatar_url,
            role_id=user_data.role_id,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create default settings
        settings = UserSettingsDB(
            user_id=user.id,
            preferences={},
            theme="light",
            language="en",
            notification_email=True,
            notification_web=True,
            timezone="UTC",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(settings)
        db.commit()

        # Audit log
        self.create_audit_log(
            db=db,
            user_id=admin_user_id,
            action="create_user",
            entity_type="user",
            entity_id=str(user.id),
            details={"username": user.username, "email": user.email, "role_id": user.role_id},
            ip_address=None,
            user_agent=None,
        )

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            role=role.name,
            role_id=role.id,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def update_user(
        self,
        db: Session,
        user_id: int,
        update_data: UserUpdateRequest,
        current_user_id: int,
    ) -> UserResponse:
        """Update user."""
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Update fields
        if update_data.username:
            existing = (
                db.query(UserDB)
                .filter(UserDB.username == update_data.username, UserDB.id != user_id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
                )
            user.username = update_data.username

        if update_data.email:
            existing = (
                db.query(UserDB)
                .filter(UserDB.email == update_data.email, UserDB.id != user_id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
                )
            user.email = update_data.email

        if update_data.avatar_url is not None:
            user.avatar_url = update_data.avatar_url

        if update_data.role_id is not None:
            role = db.query(RoleDB).filter(RoleDB.id == update_data.role_id).first()
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found"
                )
            user.role_id = update_data.role_id

        if update_data.is_active is not None:
            user.is_active = update_data.is_active

        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        # Audit log
        self.create_audit_log(
            db=db,
            user_id=current_user_id,
            action="update_user",
            entity_type="user",
            entity_id=str(user.id),
            details={"updated_fields": update_data.model_dump(exclude_none=True)},
            ip_address=None,
            user_agent=None,
        )

        role = db.query(RoleDB).filter(RoleDB.id == user.role_id).first()
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            role=role.name if role else "unknown",
            role_id=user.role_id,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def delete_user(self, db: Session, user_id: int, current_user_id: int) -> None:
        """Delete a user."""
        if user_id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself"
            )

        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Audit log before deletion
        self.create_audit_log(
            db=db,
            user_id=current_user_id,
            action="delete_user",
            entity_type="user",
            entity_id=str(user.id),
            details={"username": user.username, "email": user.email},
            ip_address=None,
            user_agent=None,
        )

        # Delete user (cascade will delete settings, notifications)
        db.delete(user)
        db.commit()

    # User Settings

    def get_user_settings(self, db: Session, user_id: int) -> UserSettingsResponse:
        """Get user settings."""
        settings = db.query(UserSettingsDB).filter(UserSettingsDB.user_id == user_id).first()
        if not settings:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")

        return UserSettingsResponse(
            id=settings.id,
            user_id=settings.user_id,
            preferences=settings.preferences,
            theme=settings.theme,
            language=settings.language,
            notification_email=settings.notification_email,
            notification_web=settings.notification_web,
            timezone=settings.timezone,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )

    def update_user_settings(
        self,
        db: Session,
        user_id: int,
        update_data: UserSettingsUpdateRequest,
        current_user_id: int,
    ) -> UserSettingsResponse:
        """Update user settings."""
        settings = db.query(UserSettingsDB).filter(UserSettingsDB.user_id == user_id).first()
        if not settings:
            # Create default settings if not found
            settings = UserSettingsDB(
                user_id=user_id,
                preferences={},
                theme="light",
                language="en",
                notification_email=True,
                notification_web=True,
                timezone="UTC",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)

        # Update fields
        if isinstance(update_data, UserSettingsUpdateRequest):
            if update_data.preferences is not None:
                settings.preferences = update_data.preferences
            if update_data.theme is not None:
                settings.theme = update_data.theme
            if update_data.language is not None:
                settings.language = update_data.language
            if update_data.timezone is not None:
                settings.timezone = update_data.timezone
            if update_data.notification_email is not None:
                settings.notification_email = update_data.notification_email
            if update_data.notification_web is not None:
                settings.notification_web = update_data.notification_web

        settings.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(settings)

        return UserSettingsResponse(
            id=settings.id,
            user_id=settings.user_id,
            preferences=settings.preferences,
            theme=settings.theme,
            language=settings.language,
            notification_email=settings.notification_email,
            notification_web=settings.notification_web,
            timezone=settings.timezone,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )

    # Notifications

    def list_notifications(
        self,
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ) -> NotificationListResponse:
        """List user notifications."""
        query = db.query(NotificationDB).filter(NotificationDB.user_id == user_id)

        if unread_only:
            query = query.filter(NotificationDB.read == False)

        total = query.count()
        unread_count = (
            db.query(NotificationDB)
            .filter(NotificationDB.user_id == user_id, NotificationDB.read == False)
            .count()
        )
        skip = (page - 1) * page_size
        notifications = (
            query.order_by(NotificationDB.created_at.desc()).offset(skip).limit(page_size).all()
        )

        notification_responses = [
            NotificationResponse(
                id=n.id,
                user_id=n.user_id,
                type=n.type,
                title=n.title,
                message=n.message,
                read=n.read,
                link_url=n.link_url,
                metadata=n.meta_data,
                created_at=n.created_at,
            )
            for n in notifications
        ]

        return NotificationListResponse(
            notifications=notification_responses,
            total=total,
            unread_count=unread_count,
            page=page,
            page_size=page_size,
        )

    def update_notification(
        self,
        db: Session,
        user_id: int,
        notification_id: int,
        update_data: NotificationUpdateRequest,
    ) -> NotificationResponse:
        """Update notification (mark as read/unread)."""
        notification = (
            db.query(NotificationDB)
            .filter(NotificationDB.id == notification_id, NotificationDB.user_id == user_id)
            .first()
        )
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
            )

        notification.read = update_data.read
        db.commit()
        db.refresh(notification)

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

    def mark_all_notifications_read(self, db: Session, user_id: int) -> int:
        """Mark all notifications as read."""
        notifications = (
            db.query(NotificationDB)
            .filter(NotificationDB.user_id == user_id, NotificationDB.read == False)
            .all()
        )
        count = len(notifications)
        for n in notifications:
            n.read = True
        db.commit()
        return count

    # Audit Logs

    def list_audit_logs(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        user_id_filter: Optional[int] = None,
    ) -> AuditLogListResponse:
        """List audit logs."""
        query = db.query(AuditLogDB)

        if user_id_filter:
            query = query.filter(AuditLogDB.user_id == user_id_filter)

        total = query.count()
        skip = (page - 1) * page_size
        audit_logs = (
            query.order_by(AuditLogDB.created_at.desc()).offset(skip).limit(page_size).all()
        )

        log_responses = []
        for log in audit_logs:
            username = None
            if log.user_id:
                user = db.query(UserDB).filter(UserDB.id == log.user_id).first()
                if user:
                    username = user.username

            log_responses.append(
                AuditLogResponse(
                    id=log.id,
                    user_id=log.user_id,
                    username=username,
                    action=log.action,
                    entity_type=log.entity_type,
                    entity_id=log.entity_id,
                    details=log.details,
                    ip_address=log.ip_address,
                    user_agent=log.user_agent,
                    created_at=log.created_at,
                )
            )

        return AuditLogListResponse(
            audit_logs=log_responses, total=total, page=page, page_size=page_size
        )
