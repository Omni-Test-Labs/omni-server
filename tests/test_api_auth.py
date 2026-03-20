"""Tests for authentication API endpoints."""

import pytest
from fastapi import status

# Import models to ensure they're registered with SQLAlchemy
from omni_server import models


class TestRegisterEndpoint:
    """Test POST /api/auth/register endpoint."""

    def test_register_new_user(self, client):
        """Test registering a new user."""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePass123",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "password" not in data
        assert "id" in data

    def test_register_duplicate_username(self, client):
        """Test registering with duplicate username."""
        user_data = {
            "username": "duplicate",
            "email": "user1@example.com",
            "password": "SecurePass123",
        }

        # First registration
        client.post("/api/auth/register", json=user_data)

        # Try duplicate username with different email
        duplicate_data = {
            "username": "duplicate",
            "email": "user2@example.com",
            "password": "SecurePass123",
        }

        response = client.post("/api/auth/register", json=duplicate_data)

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_register_duplicate_email(self, client):
        """Test registering with duplicate email."""
        user_data = {
            "username": "user1",
            "email": "duplicate@example.com",
            "password": "SecurePass123",
        }

        # First registration
        client.post("/api/auth/register", json=user_data)

        # Try duplicate email with different username
        duplicate_data = {
            "username": "user2",
            "email": "duplicate@example.com",
            "password": "SecurePass123",
        }

        response = client.post("/api/auth/register", json=duplicate_data)

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_register_missing_fields(self, client):
        """Test registering with missing required fields."""
        incomplete_data = {"username": "incomplete"}

        response = client.post("/api/auth/register", json=incomplete_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginEndpoint:
    """Test POST /api/auth/login endpoint."""

    def test_login_with_valid_credentials(self, client):
        """Test login with valid username and password."""
        # First register a user
        user_data = {
            "username": "testlogin",
            "email": "testlogin@example.com",
            "password": "LoginPass123",
        }
        client.post("/api/auth/register", json=user_data)

        # Login with username
        login_response = client.post(
            "/api/auth/login",
            json={"identifier": "testlogin", "password": "LoginPass123"},
        )

        assert login_response.status_code == status.HTTP_200_OK
        data = login_response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_login_with_email(self, client):
        """Test login with email instead of username."""
        # Register user
        user_data = {
            "username": "emailuser",
            "email": "emailuser@example.com",
            "password": "EmailPass123",
        }
        client.post("/api/auth/register", json=user_data)

        # Login with email
        login_response = client.post(
            "/api/auth/login",
            json={"identifier": "emailuser@example.com", "password": "EmailPass123"},
        )

        assert login_response.status_code == status.HTTP_200_OK
        data = login_response.json()
        assert "access_token" in data

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/auth/login", json={"identifier": "nonexistent", "password": "WrongPass123"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_wrong_password(self, client):
        """Test login with correct username but wrong password."""
        # Register user
        user_data = {
            "username": "wrongpass",
            "email": "wrongpass@example.com",
            "password": "CorrectPass123",
        }
        client.post("/api/auth/register", json=user_data)

        # Try wrong password
        response = client.post(
            "/api/auth/login", json={"identifier": "wrongpass", "password": "WrongPass123"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGithubOAuth:
    """Test GitHub OAuth endpoints."""

    def test_github_oauth_redirect(self, client):
        """Test GET /api/auth/oauth/github returns redirect URL."""
        # Note: request_url parameter is required by route but not used
        response = client.get("/api/auth/oauth/github?request_url=http://localhost:8000")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "redirect_url" in data
        assert "github.com" in data["redirect_url"]

    def test_github_oauth_callback_missing_state(self, client):
        """Test GitHub callback without state returns error."""
        response = client.get("/api/auth/oauth/github/callback?code=test_code&state=")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGitlabOAuth:
    """Test GitLab OAuth endpoints."""

    def test_gitlab_oauth_redirect(self, client):
        """Test GET /api/auth/oauth/gitlab returns redirect URL."""
        # Note: request_url parameter is required by route but not used
        response = client.get("/api/auth/oauth/gitlab?request_url=http://localhost:8000")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "redirect_url" in data
        assert "gitlab.com" in data["redirect_url"]

    def test_gitlab_oauth_callback_missing_state(self, client):
        """Test GitLab callback without state returns error."""
        response = client.get("/api/auth/oauth/gitlab/callback?code=test_code&state=")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestRefreshTokenEndpoint:
    """Test POST /api/auth/refresh endpoint."""

    def test_refresh_token(self, client):
        """Test refreshing access token."""
        # Register and login to get refresh token
        user_data = {
            "username": "refreshuser",
            "email": "refresh@example.com",
            "password": "RefreshPass123",
        }
        client.post("/api/auth/register", json=user_data)

        login_response = client.post(
            "/api/auth/login",
            json={"identifier": "refreshuser", "password": "RefreshPass123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        refresh_response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})

        assert refresh_response.status_code == status.HTTP_200_OK
        data = refresh_response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token."""
        response = client.post("/api/auth/refresh", json={"refresh_token": "invalid_token"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetCurrentUserEndpoint:
    """Test GET /api/auth/me endpoint (requires authentication)."""

    def test_get_current_user_info(self, client):
        """Test getting current user profile with valid token."""
        # Register and login
        user_data = {
            "username": "meuser",
            "email": "me@example.com",
            "password": "MePass123",
        }
        client.post("/api/auth/register", json=user_data)

        login_response = client.post(
            "/api/auth/login", json={"identifier": "meuser", "password": "MePass123"}
        )

        access_token = login_response.json()["access_token"]

        # Get current user info with token
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "meuser"
        assert data["email"] == "me@example.com"

    def test_get_current_user_no_token(self, client):
        """Test getting current user without token."""
        response = client.get("/api/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUpdateCurrentUserEndpoint:
    """Test PATCH /api/auth/me endpoint (requires authentication)."""

    def test_update_current_user_email(self, client):
        """Test updating current user email."""
        # Register and login
        user_data = {
            "username": "updateuser",
            "email": "update@example.com",
            "password": "UpdatePass123",
        }
        client.post("/api/auth/register", json=user_data)

        login_response = client.post(
            "/api/auth/login", json={"identifier": "updateuser", "password": "UpdatePass123"}
        )

        access_token = login_response.json()["access_token"]

        # Update email
        headers = {"Authorization": f"Bearer {access_token}"}
        update_response = client.patch(
            "/api/auth/me", json={"email": "newemail@example.com"}, headers=headers
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["email"] == "newemail@example.com"

    def test_update_current_user_no_token(self, client):
        """Test updating current user without token."""
        response = client.patch("/api/auth/me", json={"email": "new@example.com"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogoutEndpoint:
    """Test POST /api/auth/logout endpoint (requires authentication)."""

    def test_logout_with_valid_token(self, client):
        """Test logout with valid token."""
        # Register and login
        user_data = {
            "username": "logoutuser",
            "email": "logout@example.com",
            "password": "LogoutPass123",
        }
        client.post("/api/auth/register", json=user_data)

        login_response = client.post(
            "/api/auth/login", json={"identifier": "logoutuser", "password": "LogoutPass123"}
        )

        access_token = login_response.json()["access_token"]

        # Logout (client-side token deletion)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/api/auth/logout", headers=headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_no_token(self, client):
        """Test logout without token."""
        response = client.post("/api/auth/logout")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAuthFlowIntegration:
    """Test complete authentication flow integration."""

    def test_complete_auth_flow(self, client):
        """Test register -> login -> access protected resource -> logout."""
        # 1. Register
        user_data = {
            "username": "flowuser",
            "email": "flow@example.com",
            "password": "FlowPass123",
        }
        register_response = client.post("/api/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # 2. Login
        login_response = client.post(
            "/api/auth/login", json={"identifier": "flowuser", "password": "FlowPass123"}
        )
        assert login_response.status_code == status.HTTP_200_OK
        tokens = login_response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # 3. Access protected resource
        headers = {"Authorization": f"Bearer {access_token}"}
        me_response = client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == status.HTTP_200_OK

        # 4. Refresh token
        refresh_response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh_response.status_code == status.HTTP_200_OK

        # 5. Logout
        logout_response = client.post("/api/auth/logout", headers=headers)
        assert logout_response.status_code == status.HTTP_204_NO_CONTENT
