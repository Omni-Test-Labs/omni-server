"""Tests for user management admin module."""

import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException

from omni_server.models import UserDB, RoleDB, NotificationDB
from omni_server.config import Settings
from omni_server.auth.service import AuthService
from omni_server.admin.users.service import UserService
from omni_server.admin.users.models import (
    UserUpdateRequest,
    NotificationUpdateRequest,
)


@pytest.fixture
def user_service(db: Session, auth_service: AuthService):
    """Create user service fixture."""
    return UserService(auth_service)


@pytest.fixture
def test_user(db: Session, test_role: RoleDB):
    """Create test user."""
    from omni_server.auth.models import UserRegisterRequest

    settings = Settings()
    auth_service = AuthService(settings)

    user_data = UserRegisterRequest(
        username="testuser", email="test@example.com", password="TestPass123"
    )
    return auth_service.register_user(db, user_data)


class TestUserService:
    """Test UserService methods."""

    def test_list_users(self, user_service: UserService, test_user, db: Session):
        """Test listing users."""
        result = user_service.list_users(db, page=1, page_size=10)

        assert len(result.users) >= 1
        assert result.total >= 1
        assert result.page == 1

    def test_get_user(self, user_service: UserService, test_user: UserDB, db: Session):
        """Test getting user by ID."""
        result = user_service.get_user(db, test_user.id)

        assert result.username == "testuser"
        assert result.email == "test@example.com"

    def test_get_user_not_found(self, user_service: UserService, db: Session):
        """Test getting non-existent user."""
        with pytest.raises(HTTPException) as exc_info:
            user_service.get_user(db, 99999)

        assert exc_info.value.status_code == 404

    def test_create_user(
        self, user_service: UserService, test_role: RoleDB, test_user: UserDB, db: Session
    ):
        """Test creating a user."""
        from omni_server.admin.users.models import UserCreateAdminRequest

        create_data = UserCreateAdminRequest(
            username="adminuser",
            email="admin@example.com",
            password="AdminPass123",
            role_id=test_role.id,
        )

        result = user_service.create_user(db, create_data, test_user.id)

        assert result.username == "adminuser"
        assert result.email == "admin@example.com"

    def test_update_user(self, user_service: UserService, test_user: UserDB, db: Session):
        """Test updating user info."""
        update_data = UserUpdateRequest(email="updated@example.com")

        result = user_service.update_user(db, test_user.id, update_data, test_user.id)

        assert result.email == "updated@example.com"

    def test_delete_user(self, user_service: UserService, test_user: UserDB, db: Session):
        """Test deleting user."""
        # Create a user to delete
        from omni_server.auth.models import UserRegisterRequest
        from omni_server.config import Settings

        settings = Settings()
        auth_service = AuthService(settings)

        user_data = UserRegisterRequest(
            username="deleteme", email="deleteme@example.com", password="TestPass123"
        )
        user_to_delete = auth_service.register_user(db, user_data)

        # Delete user
        user_service.delete_user(db, user_to_delete.id, test_user.id)

        # Verify deletion
        assert db.query(UserDB).filter(UserDB.id == user_to_delete.id).first() is None

    def test_get_user_settings(self, user_service: UserService, test_user: UserDB, db: Session):
        """Test getting user settings."""
        result = user_service.get_user_settings(db, test_user.id)

        assert result.user_id == test_user.id
        assert result.theme == "light"

    def test_list_notifications(self, user_service: UserService, test_user: UserDB, db: Session):
        """Test listing notifications."""
        # Create a notification
        notification = NotificationDB(
            user_id=test_user.id,
            type="info",
            title="Test",
            message="Test notification",
        )
        db.add(notification)
        db.commit()

        result = user_service.list_notifications(db, test_user.id)

        assert len(result.notifications) >= 1
        assert result.total >= 1

    def test_update_notification(self, user_service: UserService, test_user: UserDB, db: Session):
        """Test updating notification."""
        # Create notification
        notification = NotificationDB(
            user_id=test_user.id,
            type="info",
            title="Test",
            message="Test notification",
            read=False,
        )
        db.add(notification)
        db.flush()

        # Update notification
        update_data = NotificationUpdateRequest(read=True)
        result = user_service.update_notification(db, test_user.id, notification.id, update_data)

        assert result.read is True

    def test_mark_all_notifications_read(
        self, user_service: UserService, test_user: UserDB, db: Session
    ):
        """Test marking all notifications as read."""
        # Create multiple notifications
        for i in range(3):
            notification = NotificationDB(
                user_id=test_user.id,
                type="info",
                title=f"Test {i}",
                message=f"Test notification {i}",
                read=False,
            )
            db.add(notification)
        db.commit()

        count = user_service.mark_all_notifications_read(db, test_user.id)

        assert count == 3
