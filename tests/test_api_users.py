"""Tests for users API endpoints."""

import pytest
from fastapi import status

# Import models to ensure they're registered with SQLAlchemy
from omni_server import models


class TestListUsersEndpoint:
    """Test GET /api/users endpoint."""

    def test_list_users_empty(self, client, auth_headers):
        """Test listing users when empty."""
        response = client.get("/api/users", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert len(data["users"]) >= 0

    def test_list_users_with_pagination(self, client, auth_headers):
        """Test listing users with pagination parameters."""
        # Create some users
        for i in range(5):
            user_data = {
                "username": f"listuser{i}",
                "email": f"listuser{i}@example.com",
                "password": "Password123",
            }
            client.post("/api/auth/register", json=user_data)

        # Request page 2 with page size 2
        response = client.get("/api/users?page=2&page_size=2", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 2

    def test_list_users_unauthorized(self, client):
        """Test listing users without authentication."""
        response = client.get("/api/users")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetUserEndpoint:
    """Test GET /api/users/{user_id} endpoint."""

    def test_get_user_by_id(self, client, auth_headers):
        """Test getting user by ID."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        # Get user by ID
        response = client.get(f"/api/users/{user_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == user_id
        assert "username" in data
        assert "email" in data

    def test_get_nonexistent_user(self, client, auth_headers):
        """Test getting non-existent user."""
        response = client.get("/api/users/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_user_unauthorized(self, client):
        """Test getting user without authentication."""
        response = client.get("/api/users/1")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCreateUserEndpoint:
    """Test POST /api/users endpoint (admin only)."""

    def test_create_user(self, client, auth_headers):
        """Test creating a new user."""
        user_data = {
            "username": "newadminuser",
            "email": "newadmin@example.com",
            "password": "SecurePass123",
            "role_id": 1,
        }

        response = client.post("/api/users", json=user_data, headers=auth_headers)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "newadminuser"
        assert data["email"] == "newadmin@example.com"

    def test_create_user_duplicate_username(self, client, auth_headers):
        """Test creating user with duplicate username."""
        user_data = {
            "username": "duplicate",
            "email": "user1@example.com",
            "password": "SecurePass123",
            "role_id": 1,
        }

        # First user
        client.post("/api/users", json=user_data, headers=auth_headers)

        # Second user with same username
        duplicate_data = {
            "username": "duplicate",
            "email": "user2@example.com",
            "password": "SecurePass123",
            "role_id": 1,
        }

        response = client.post("/api/users", json=duplicate_data, headers=auth_headers)

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_user_unauthorized(self, client):
        """Test creating user without authentication."""
        user_data = {
            "username": "unauth",
            "email": "unauth@example.com",
            "password": "Pass123",
            "role_id": 1,
        }

        response = client.post("/api/users", json=user_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUpdateUserEndpoint:
    """Test PATCH /api/users/{user_id} endpoint."""

    def test_update_user_email(self, client, auth_headers):
        """Test updating user email."""
        # Create a user first
        user_data = {
            "username": "updateme",
            "email": "updateme@example.com",
            "password": "UpdatePass123",
            "role_id": 1,
        }
        create_response = client.post("/api/users", json=user_data, headers=auth_headers)
        user_id = create_response.json()["id"]

        # Update email
        update_data = {"email": "updated@example.com"}
        response = client.patch(f"/api/users/{user_id}", json=update_data, headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "updated@example.com"

    def test_update_nonexistent_user(self, client, auth_headers):
        """Test updating non-existent user."""
        update_data = {"email": "test@example.com"}
        response = client.patch("/api/users/99999", json=update_data, headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_user_unauthorized(self, client):
        """Test updating user without authentication."""
        update_data = {"email": "test@example.com"}
        response = client.patch("/api/users/1", json=update_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestDeleteUserEndpoint:
    """Test DELETE /api/users/{user_id} endpoint."""

    def test_delete_user(self, client, auth_headers):
        """Test deleting a user."""
        # Create a user first
        user_data = {
            "username": "deleteme",
            "email": "deleteme@example.com",
            "password": "DeletePass123",
            "role_id": 1,
        }
        create_response = client.post("/api/users", json=user_data, headers=auth_headers)
        user_id = create_response.json()["id"]

        # Delete user
        response = client.delete(f"/api/users/{user_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_nonexistent_user(self, client, auth_headers):
        """Test deleting non-existent user."""
        response = client.delete("/api/users/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_user_unauthorized(self, client):
        """Test deleting user without authentication."""
        response = client.delete("/api/users/1")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUserSettingsEndpoints:
    """Test user settings endpoints."""

    def test_get_user_settings(self, client, auth_headers):
        """Test getting user settings."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        # Get user settings
        response = client.get(f"/api/users/{user_id}/settings", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_id"] == user_id
        assert "theme" in data
        assert "language" in data

    def test_get_nonexistent_user_settings(self, client, auth_headers):
        """Test getting settings for non-existent user."""
        response = client.get("/api/users/99999/settings", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_user_settings(self, client, auth_headers):
        """Test updating user settings."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        # Update settings
        update_data = {
            "theme": "dark",
            "language": "zh",
            "notification_email": False,
        }
        response = client.patch(
            f"/api/users/{user_id}/settings", json=update_data, headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["theme"] == "dark"
        assert data["language"] == "zh"

    def test_update_settings_unauthorized(self, client):
        """Test updating settings without authentication."""
        update_data = {"theme": "dark"}
        response = client.patch("/api/users/1/settings", json=update_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUserNotificationsEndpoints:
    """Test user notifications endpoints."""

    def test_list_notifications_empty(self, client, auth_headers):
        """Test listing notifications when empty."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        # List notifications
        response = client.get(f"/api/users/{user_id}/notifications", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "notifications" in data
        assert "total" in data

    def test_list_notifications_with_unread_filter(self, client, auth_headers):
        """Test listing notifications with unread_only filter."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        # List unread notifications
        response = client.get(
            f"/api/users/{user_id}/notifications?unread_only=true", headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "notifications" in data

    def test_get_notification_by_id(self, client, auth_headers, db):
        """Test getting notification by ID."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        # Create a notification manually
        notification = models.NotificationDB(
            user_id=user_id,
            type="info",
            title="Test Notification",
            message="This is a test notification",
            read=False,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)

        # Get notification by ID
        response = client.get(
            f"/api/users/{user_id}/notifications/{notification.id}", headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == notification.id
        assert data["title"] == "Test Notification"

    def test_nonexistent_notification(self, client, auth_headers):
        """Test getting non-existent notification."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        response = client.get(f"/api/users/{user_id}/notifications/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_notification(self, client, auth_headers, db):
        """Test updating notification (mark as read)."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        # Create a notification manually
        notification = models.NotificationDB(
            user_id=user_id,
            type="info",
            title="Test Notification",
            message="This is a test notification",
            read=False,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)

        # Update notification
        update_data = {"read": True}
        response = client.patch(
            f"/api/users/{user_id}/notifications/{notification.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["read"] is True

    def test_mark_all_notifications_read(self, client, auth_headers, db):
        """Test marking all notifications as read."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        # Create multiple notifications
        for i in range(3):
            notification = models.NotificationDB(
                user_id=user_id,
                type="info",
                title=f"Test Notification {i}",
                message=f"This is test notification {i}",
                read=False,
            )
            db.add(notification)
        db.commit()

        # Mark all as read
        response = client.post(
            f"/api/users/{user_id}/notifications/mark-all-read",
            json={"mark_as_read": True},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "count" in data
        assert data["count"] >= 3

    def test_notifications_unauthorized(self, client):
        """Test accessing notifications without authentication."""
        response = client.get("/api/users/1/notifications")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAuditLogsEndpoint:
    """Test GET /api/audit-logs endpoint."""

    def test_list_audit_logs_empty(self, client, auth_headers):
        """Test listing audit logs when empty."""
        response = client.get("/api/audit-logs", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "audit_logs" in data
        assert "total" in data
        assert "page" in data

    def test_list_audit_logs_with_pagination(self, client, auth_headers):
        """Test listing audit logs with pagination."""
        response = client.get("/api/audit-logs?page=1&page_size=20", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_audit_logs_by_user_id(self, client, auth_headers):
        """Test listing audit logs filtered by user ID."""
        # First get current user info to get user ID
        me_response = client.get("/api/auth/me", headers=auth_headers)
        user_id = me_response.json()["id"]

        # List audit logs for specific user
        response = client.get(f"/api/audit-logs?user_id={user_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "audit_logs" in data

    def test_list_audit_logs_unauthorized(self, client):
        """Test listing audit logs without authentication."""
        response = client.get("/api/audit-logs")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUsersApiIntegration:
    """Test complete user management flow integration."""

    def test_complete_user_lifecycle(self, client, auth_headers):
        """Test create -> read -> update -> delete user lifecycle."""
        # 1. Create user
        user_data = {
            "username": "lifecycle",
            "email": "lifecycle@example.com",
            "password": "LifePass123",
            "role_id": 1,
        }
        create_response = client.post("/api/users", json=user_data, headers=auth_headers)
        assert create_response.status_code == status.HTTP_201_CREATED
        user_id = create_response.json()["id"]

        # 2. Read user
        get_response = client.get(f"/api/users/{user_id}", headers=auth_headers)
        assert get_response.status_code == status.HTTP_200_OK

        # 3. Update user
        update_data = {"email": "updated@example.com"}
        update_response = client.patch(
            f"/api/users/{user_id}", json=update_data, headers=auth_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["email"] == "updated@example.com"

        # 4. Delete user
        delete_response = client.delete(f"/api/users/{user_id}", headers=auth_headers)
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # 5. Verify deletion (should get 404)
        verify_response = client.get(f"/api/users/{user_id}", headers=auth_headers)
        assert verify_response.status_code == status.HTTP_404_NOT_FOUND
