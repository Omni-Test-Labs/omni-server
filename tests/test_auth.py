"""Tests for authentication module."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from omni_server.models import UserDB, RoleDB, UserSettingsDB
from omni_server.config import Settings
from omni_server.auth.service import AuthService
from omni_server.auth.models import (
    UserRegisterRequest,
    UserLoginRequest,
    UserUpdateRequest,
    TokenRefreshRequest,
)


class TestAuthService:
    """Test AuthService methods."""

    def test_hash_password(self, auth_service: AuthService):
        """Test password hashing."""
        password = "TestPass123"
        hashed = auth_service.hash_password(password)

        assert hashed != password
        assert len(hashed) > 50
        assert isinstance(hashed, str)

    def test_verify_password(self, auth_service: AuthService):
        """Test password verification."""
        password = "TestPass123"
        hashed = auth_service.hash_password(password)

        assert auth_service.verify_password(password, hashed) is True
        assert auth_service.verify_password("WrongPassword", hashed) is False

    def test_register_user(self, auth_service: AuthService, test_role: RoleDB, db: Session):
        """Test user registration."""
        user_data = UserRegisterRequest(
            username="testuser", email="test@example.com", password="TestPass123"
        )

        result = auth_service.register_user(db, user_data)

        assert result.username == "testuser"
        assert result.email == "test@example.com"
        assert result.is_active is True

        # Verify user was created in DB
        user = db.query(UserDB).filter(UserDB.username == "testuser").first()
        assert user is not None

        # Verify settings were created
        settings = db.query(UserSettingsDB).filter(UserSettingsDB.user_id == user.id).first()
        assert settings is not None

    def test_register_duplicate_username(
        self, auth_service: AuthService, test_role: RoleDB, db: Session
    ):
        """Test registration with duplicate username."""
        user_data = UserRegisterRequest(
            username="testuser", email="test1@example.com", password="TestPass123"
        )

        # First registration
        auth_service.register_user(db, user_data)

        # Duplicate username should fail
        user_data.email = "test2@example.com"
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            auth_service.register_user(db, user_data)

        assert exc_info.value.status_code == 409

    def test_register_duplicate_email(
        self, auth_service: AuthService, test_role: RoleDB, db: Session
    ):
        """Test registration with duplicate email."""
        user_data = UserRegisterRequest(
            username="testuser1", email="test@example.com", password="TestPass123"
        )

        # First registration
        auth_service.register_user(db, user_data)

        # Duplicate email should fail
        user_data.username = "testuser2"
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            auth_service.register_user(db, user_data)

        assert exc_info.value.status_code == 409

    def test_login_user(self, auth_service: AuthService, test_role: RoleDB, db: Session):
        """Test user login."""
        # Register user first
        user_data = UserRegisterRequest(
            username="testuser", email="test@example.com", password="TestPass123"
        )
        auth_service.register_user(db, user_data)

        # Login
        login_data = UserLoginRequest(identifier="testuser", password="TestPass123")
        result = auth_service.login_user(db, login_data)

        assert "access_token" in result.__dict__
        assert "refresh_token" in result.__dict__
        assert result.token_type == "bearer"
        assert result.expires_in > 0

    def test_login_invalid_credentials(self, auth_service: AuthService, db: Session):
        """Test login with invalid credentials."""
        login_data = UserLoginRequest(identifier="nonexistent", password="WrongPass123")

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            auth_service.login_user(db, login_data)

        assert exc_info.value.status_code == 401

    def test_get_user_by_id(self, auth_service: AuthService, test_role: RoleDB, db: Session):
        """Test getting user by ID."""
        # Register user
        user_data = UserRegisterRequest(
            username="testuser", email="test@example.com", password="TestPass123"
        )
        registered_user = auth_service.register_user(db, user_data)

        # Get user
        result = auth_service.get_user_by_id(db, registered_user.id)

        assert result.username == "testuser"
        assert result.email == "test@example.com"
        assert result.settings is not None

    def test_update_user(self, auth_service: AuthService, test_role: RoleDB, db: Session):
        """Test updating user."""
        # Register user
        user_data = UserRegisterRequest(
            username="testuser", email="test@example.com", password="TestPass123"
        )
        registered_user = auth_service.register_user(db, user_data)

        # Update user
        update_data = UserUpdateRequest(email="newemail@example.com")
        result = auth_service.update_user(db, registered_user.id, update_data)

        assert result.email == "newemail@example.com"

    def test_create_access_token(self, auth_service: AuthService):
        """Test JWT access token creation."""
        token = auth_service.create_access_token(1, "testuser", 1)

        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_refresh_token(self, auth_service: AuthService):
        """Test JWT refresh token creation."""
        token = auth_service.create_refresh_token(1)

        assert isinstance(token, str)
        assert len(token) > 20

    def test_decode_token(self, auth_service: AuthService):
        """Test JWT token decoding."""
        token = auth_service.create_access_token(1, "testuser", 1)
        payload = auth_service._decode_token(token)

        assert payload["sub"] == "1"
        assert payload["username"] == "testuser"
        assert payload["role_id"] == 1
        assert payload["type"] == "access"

    def test_decode_invalid_token(self, auth_service: AuthService):
        """Test decoding invalid token."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            auth_service._decode_token("invalid_token")

        assert exc_info.value.status_code == 401
