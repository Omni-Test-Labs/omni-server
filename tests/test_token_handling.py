"""JWT token handling tests - structural validation, expiry, and error handling."""

from datetime import datetime, timedelta
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from omni_server.auth.service import AuthService
from omni_server.config import Settings
from omni_server.auth.routes import auth_service


class TestTokenStructureValidation:
    """Test JWT token structure and content."""

    def test_access_token_has_required_claims(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        token = auth_service.create_access_token(user_id=1, username="testuser", role_id=2)

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        assert "sub" in payload
        assert "username" in payload
        assert "role_id" in payload
        assert "type" in payload
        assert "exp" in payload

        assert payload["sub"] == "1"
        assert payload["username"] == "testuser"
        assert payload["role_id"] == 2
        assert payload["type"] == "access"

    def test_refresh_token_has_required_claims(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        token = auth_service.create_refresh_token(user_id=1)

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        assert "sub" in payload
        assert "type" in payload
        assert "exp" in payload

        assert payload["sub"] == "1"
        assert payload["type"] == "refresh"
        assert "username" not in payload
        assert "role_id" not in payload

    def test_access_token_expires_in_future(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        token = auth_service.create_access_token(user_id=1, username="testuser", role_id=2)

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        exp = payload["exp"]
        now = datetime.utcnow()

        assert exp > now.timestamp()

    def test_refresh_token_expires_in_future(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        token = auth_service.create_refresh_token(user_id=1)

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        exp = payload["exp"]
        now = datetime.utcnow()

        assert exp > now.timestamp()

    def test_token_type_differentiates_access_and_refresh(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        access_token = auth_service.create_access_token(user_id=1, username="testuser", role_id=2)
        refresh_token = auth_service.create_refresh_token(user_id=1)

        access_payload = jwt.decode(
            access_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        refresh_payload = jwt.decode(
            refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"
        assert access_payload["type"] != refresh_payload["type"]


class TestTokenErrorHandling:
    """Test token validation errors and edge cases."""

    def test_expired_token_rejected(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        payload = {
            "sub": "1",
            "username": "testuser",
            "role_id": 2,
            "type": "access",
            "exp": datetime.utcnow() - timedelta(minutes=1),
        }
        expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        with pytest.raises(Exception) as exc_info:
            auth_service._decode_token(expired_token)

        assert exc_info.value.status_code == 401
        assert "credentials" in str(exc_info.value.detail).lower()

    def test_invalid_token_format_rejected(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        invalid_tokens = [
            "",
            "invalid.token.format",
            "not.a.jwt.at.all!!!",
            "Bearer invalid",
        ]

        for invalid_token in invalid_tokens:
            with pytest.raises(Exception) as exc_info:
                auth_service._decode_token(invalid_token)

            assert exc_info.value.status_code == 401

    def test_token_wrong_secret_rejected(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        token = auth_service.create_access_token(user_id=1, username="testuser", role_id=2)

        with pytest.raises(Exception):
            jwt.decode(
                token,
                "wrong-secret-key",
                algorithms=[settings.jwt_algorithm],
            )

    def test_token_wrong_algorithm_rejected(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        token = auth_service.create_access_token(user_id=1, username="testuser", role_id=2)

        with pytest.raises(JWTError):
            jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=["HS512"],
            )

    def test_refresh_token_used_as_access_token_fails(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        refresh_token = auth_service.create_refresh_token(user_id=1)

        payload = jwt.decode(
            refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["type"] == "refresh"

        from fastapi import HTTPException

        decoded_payload = auth_service._decode_token(refresh_token)

        if decoded_payload.get("type") != "access":
            with pytest.raises(HTTPException) as exc_info:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token type",
                )
            assert exc_info.value.status_code == 401


class TestTokenRefreshEndpoint:
    """Test refresh token endpoint functionality."""

    def test_refresh_endpoint_returns_new_tokens(self, client: TestClient, test_user: dict):
        refresh_token = auth_service.create_refresh_token(user_id=test_user["id"])

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert "expires_in" in data
        assert "refresh_expires_in" in data

        assert data["token_type"] == "bearer"
        assert data["access_token"] != refresh_token
        assert data["access_token"] != test_user.get("access_token", "")

    def test_refresh_endpoint_with_invalid_token_rejected(self, client: TestClient):
        invalid_tokens = [
            "",
            "invalid.token.format",
            "not-a-real-token",
        ]

        for invalid_token in invalid_tokens:
            response = client.post(
                "/api/auth/refresh",
                json={"refresh_token": invalid_token}
            )

            assert response.status_code == 401

    def test_refresh_endpoint_with_access_token_rejected(self, client: TestClient, test_user: dict):
        access_token = auth_service.create_access_token(
            user_id=test_user["id"],
            username=test_user["username"],
            role_id=test_user["role_id"]
        )

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": access_token}
        )

        assert response.status_code == 401
        data = response.json()
        assert "credentials" in str(data.get("detail", "")).lower()

    def test_refresh_with_nonexistent_user_rejected(self, client: TestClient, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        refresh_token = auth_service.create_refresh_token(user_id=99999)

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 401
        data = response.json()
        assert "user" in str(data.get("detail", "")).lower()

    def test_refresh_endpoint_user_inactive_rejected(self, client: TestClient, test_db: Session):
        from omni_server.models import UserDB

        settings = Settings()
        auth_service = AuthService(settings)

        user = UserDB(
            username="inactive_user",
            email="inactive@test.com",
            hashed_password=auth_service.hash_password("password123"),
            role_id=1,
            is_active=False,
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        refresh_token = auth_service.create_refresh_token(user_id=user.id)

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 403
        data = response.json()
        assert "inactive" in str(data.get("detail", "")).lower()


class TestCurrentUserEndpoint:
    """Test get_current_user functionality."""

    def test_get_current_user_with_valid_token(self, client: TestClient, test_user: dict):
        access_token = test_user.get("access_token")

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200

        data = response.json()
        assert data["id"] == test_user["id"]
        assert data["username"] == test_user["username"]
        assert data["email"] == test_user["email"]
        assert data["is_active"] is True

    def test_get_current_user_with_invalid_token(self, client: TestClient):
        invalid_tokens = [
            "",
            "Bearer invalid",
            "not.a.jwt",
        ]

        for token in invalid_tokens:
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": token}
            )

            assert response.status_code == 401

    def test_get_current_user_without_token(self, client: TestClient):
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_get_current_user_with_expired_token(self, client: TestClient, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        payload = {
            "sub": "1",
            "username": "testuser",
            "role_id": 2,
            "type": "access",
            "exp": datetime.utcnow() - timedelta(minutes=1),
        }
        expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401


class TestTokenSecurity:
    """Security tests for token handling."""

    def test_token_uses_hs256_algorithm(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        token = auth_service.create_access_token(user_id=1, username="testuser", role_id=2)

        header = jwt.get_unverified_header(token)

        assert header["alg"] == "HS256"

    def test_token_sub_claim_is_string(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        token = auth_service.create_access_token(user_id=123, username="testuser", role_id=2)

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        assert isinstance(payload["sub"], str)
        assert payload["sub"] == "123"

    def test_multiple_tokens_same_payload_same_signature(self, test_db: Session):
        settings = Settings()
        auth_service = AuthService(settings)

        user_id = 1
        username = "testuser"
        role_id = 2

        tokens = [
            auth_service.create_access_token(user_id, username, role_id),
            auth_service.create_access_token(user_id, username, role_id),
            auth_service.create_access_token(user_id, username, role_id),
        ]

        assert len(tokens) == 3
        assert len(set(tokens)) == 1

    def test_refresh_tokens_are_different_on_each_refresh(self, client: TestClient, test_user: dict):
        refresh_token_1 = auth_service.create_refresh_token(user_id=test_user["id"])

        response_1 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token_1}
        )
        data_1 = response_1.json()
        new_refresh_token_1 = data_1["refresh_token"]

        response_2 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": new_refresh_token_1}
        )
        data_2 = response_2.json()
        new_refresh_token_2 = data_2["refresh_token"]

        assert refresh_token_1 != new_refresh_token_1
        assert new_refresh_token_1 != new_refresh_token_2
        assert refresh_token_1 != new_refresh_token_2
