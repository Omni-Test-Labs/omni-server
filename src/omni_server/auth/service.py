"""Authentication service for JWT, password hashing, and OAuth integration."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import RoleDB, UserDB, UserSettingsDB
from .models import (
    TokenResponse,
    UserDetailResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserSettingsResponse,
    UserUpdateRequest,
)


class AuthService:
    """Service for authentication and authorization operations."""

    def __init__(self, settings: Settings):
        """Initialize AuthService with configuration."""
        self.settings = settings
        self.http_client = httpx.AsyncClient(timeout=30.0)

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    def _create_token(
        self, data: dict, expires_delta: timedelta, secret: str, algorithm: str
    ) -> str:
        """Create a JWT token with expiration."""
        to_encode = data.copy()
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, secret, algorithm=algorithm)
        return encoded_jwt

    def create_access_token(self, user_id: int, username: str, role_id: int) -> str:
        """Create a JWT access token."""
        data = {"sub": str(user_id), "username": username, "role_id": role_id, "type": "access"}
        expires_delta = timedelta(minutes=self.settings.access_token_expire_minutes)
        return self._create_token(
            data,
            expires_delta,
            self.settings.jwt_secret_key,
            self.settings.jwt_algorithm,
        )

    def create_refresh_token(self, user_id: int) -> str:
        """Create a JWT refresh token."""
        data = {"sub": str(user_id), "type": "refresh"}
        expires_delta = timedelta(days=self.settings.refresh_token_expire_days)
        return self._create_token(
            data,
            expires_delta,
            self.settings.jwt_secret_key,
            self.settings.jwt_algorithm,
        )

    def _decode_token(self, token: str) -> dict:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
            return payload
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            ) from e

    def register_user(self, db: Session, user_data: UserRegisterRequest) -> UserResponse:
        """Register a new user."""
        # Check if username exists
        existing_user = db.query(UserDB).filter(UserDB.username == user_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )

        # Check if email exists
        existing_email = db.query(UserDB).filter(UserDB.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        # Get default user role
        role = db.query(RoleDB).filter(RoleDB.name == "user").first()
        if not role:
            role = db.query(RoleDB).filter(RoleDB.id == 1).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default role not found",
            )

        # Create user
        hashed_password = self.hash_password(user_data.password)
        user = UserDB(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            role_id=role.id,
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
        )
        db.add(settings)
        db.commit()

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

    def login_user(self, db: Session, login_data: UserLoginRequest) -> TokenResponse:
        """Authenticate user and return tokens."""
        # Find user by username or email
        user = (
            db.query(UserDB)
            .filter(
                (UserDB.username == login_data.identifier) | (UserDB.email == login_data.identifier)
            )
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not self.verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        # Generate tokens
        access_token = self.create_access_token(user.id, user.username, user.role_id)
        refresh_token = self.create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.settings.access_token_expire_minutes * 60,
            refresh_token=refresh_token,
            refresh_expires_in=self.settings.refresh_token_expire_days * 24 * 60 * 60,
        )

    async def refresh_tokens(self, db: Session, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token."""
        try:
            payload = jwt.decode(
                refresh_token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                )
            user_id = int(payload.get("sub"))
        except (JWTError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            ) from e

        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        # Generate new tokens
        access_token = self.create_access_token(user.id, user.username, user.role_id)
        new_refresh_token = self.create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.settings.access_token_expire_minutes * 60,
            refresh_token=new_refresh_token,
            refresh_expires_in=self.settings.refresh_token_expire_days * 24 * 60 * 60,
        )

    async def handle_github_oauth(self, db: Session, code: str) -> TokenResponse:
        """Handle GitHub OAuth callback."""
        # Exchange code for access token
        token_response = await self.http_client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": self.settings.github_client_id,
                "client_secret": self.settings.github_client_secret,
                "code": code,
                "redirect_uri": self.settings.github_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_response.json()

        if "error" in token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=token_data.get("error_description", "OAuth error"),
            )

        access_token = token_data.get("access_token")

        # Fetch user profile
        user_response = await self.http_client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"},
        )
        github_user = user_response.json()

        # Check if user exists by github_id
        user = db.query(UserDB).filter(UserDB.github_id == str(github_user["id"])).first()

        if user:
            # User exists, login
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

            # Update avatar
            if github_user.get("avatar_url") and not user.avatar_url:
                user.avatar_url = github_user["avatar_url"]
                db.commit()

            return TokenResponse(
                access_token=self.create_access_token(user.id, user.username, user.role_id),
                token_type="bearer",
                expires_in=self.settings.access_token_expire_minutes * 60,
                refresh_token=self.create_refresh_token(user.id),
                refresh_expires_in=self.settings.refresh_token_expire_days * 24 * 60 * 60,
            )
        else:
            # Create new user
            # Get default role
            role = db.query(RoleDB).filter(RoleDB.name == "user").first()
            if not role:
                role = db.query(RoleDB).filter(RoleDB.id == 1).first()
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Default role not found",
                )

            # Generate random password
            random_password = secrets.token_urlsafe(32)

            # Create username from github login or email
            username = github_user.get("login") or github_user.get("email", "").split("@")[0]
            # Ensure username is unique
            base_username = username
            counter = 1
            while db.query(UserDB).filter(UserDB.username == username).first():
                username = f"{base_username}{counter}"
                counter += 1

            user = UserDB(
                username=username,
                email=github_user.get("email", f"{username}@github.local"),
                hashed_password=self.hash_password(random_password),
                github_id=str(github_user["id"]),
                avatar_url=github_user.get("avatar_url"),
                role_id=role.id,
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
            )
            db.add(settings)
            db.commit()

            return TokenResponse(
                access_token=self.create_access_token(user.id, user.username, user.role_id),
                token_type="bearer",
                expires_in=self.settings.access_token_expire_minutes * 60,
                refresh_token=self.create_refresh_token(user.id),
                refresh_expires_in=self.settings.refresh_token_expire_days * 24 * 60 * 60,
            )

    async def handle_gitlab_oauth(self, db: Session, code: str) -> TokenResponse:
        """Handle GitLab OAuth callback."""
        # Exchange code for access token
        token_response = await self.http_client.post(
            "https://gitlab.com/oauth/token",
            data={
                "client_id": self.settings.gitlab_client_id,
                "client_secret": self.settings.gitlab_client_secret,
                "code": code,
                "redirect_uri": self.settings.gitlab_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_response.json()

        if "error" in token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=token_data.get("error_description", "OAuth error"),
            )

        access_token = token_data.get("access_token")

        # Fetch user profile
        user_response = await self.http_client.get(
            "https://gitlab.com/api/v4/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        gitlab_user = user_response.json()

        # Check if user exists by gitlab_id
        user = db.query(UserDB).filter(UserDB.gitlab_id == str(gitlab_user["id"])).first()

        if user:
            # User exists, login
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

            # Update avatar
            if gitlab_user.get("avatar_url") and not user.avatar_url:
                user.avatar_url = gitlab_user["avatar_url"]
                db.commit()

            return TokenResponse(
                access_token=self.create_access_token(user.id, user.username, user.role_id),
                token_type="bearer",
                expires_in=self.settings.access_token_expire_minutes * 60,
                refresh_token=self.create_refresh_token(user.id),
                refresh_expires_in=self.settings.refresh_token_expire_days * 24 * 60 * 60,
            )
        else:
            # Create new user
            # Get default role
            role = db.query(RoleDB).filter(RoleDB.name == "user").first()
            if not role:
                role = db.query(RoleDB).filter(RoleDB.id == 1).first()
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Default role not found",
                )

            # Generate random password
            random_password = secrets.token_urlsafe(32)

            # Create username from gitlab username or email
            username = gitlab_user.get("username") or gitlab_user.get("email", "").split("@")[0]
            # Ensure username is unique
            base_username = username
            counter = 1
            while db.query(UserDB).filter(UserDB.username == username).first():
                username = f"{base_username}{counter}"
                counter += 1

            user = UserDB(
                username=username,
                email=gitlab_user.get("email", f"{username}@gitlab.local"),
                hashed_password=self.hash_password(random_password),
                gitlab_id=str(gitlab_user["id"]),
                avatar_url=gitlab_user.get("avatar_url"),
                role_id=role.id,
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
            )
            db.add(settings)
            db.commit()

            return TokenResponse(
                access_token=self.create_access_token(user.id, user.username, user.role_id),
                token_type="bearer",
                expires_in=self.settings.access_token_expire_minutes * 60,
                refresh_token=self.create_refresh_token(user.id),
                refresh_expires_in=self.settings.refresh_token_expire_days * 24 * 60 * 60,
            )

    def get_current_user(self, db: Session, token: str) -> UserDB:
        """Get current user from JWT token."""
        payload = self._decode_token(token)

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user_id = int(payload.get("sub"))
        user = db.query(UserDB).filter(UserDB.id == user_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        return user

    def get_user_by_id(self, db: Session, user_id: int) -> UserDetailResponse:
        """Get user detail by ID."""
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        settings = db.query(UserSettingsDB).filter(
            UserSettingsDB.user_id == user_id
        ).first() or UserSettingsDB(
            user_id=user_id,
            preferences={},
            theme="light",
            language="en",
            notification_email=True,
            notification_web=True,
            timezone="UTC",
        )

        role = db.query(RoleDB).filter(RoleDB.id == user.role_id).first()

        return UserDetailResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            role=role.name if role else "unknown",
            role_id=user.role_id,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            settings=UserSettingsResponse(
                preferences=settings.preferences,
                theme=settings.theme,
                language=settings.language,
                notification_email=settings.notification_email,
                notification_web=settings.notification_web,
                timezone=settings.timezone,
            ),
        )

    def update_user(
        self, db: Session, user_id: int, update_data: UserUpdateRequest
    ) -> UserDetailResponse:
        """Update user profile."""
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Update user fields
        if update_data.email:
            # Check if email is already taken by another user
            existing = (
                db.query(UserDB)
                .filter(UserDB.email == update_data.email, UserDB.id != user_id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )
            user.email = update_data.email

        if update_data.avatar_url is not None:
            user.avatar_url = update_data.avatar_url

        user.updated_at = datetime.utcnow()

        # Update settings
        settings = db.query(UserSettingsDB).filter(
            UserSettingsDB.user_id == user_id
        ).first() or UserSettingsDB(
            user_id=user_id,
            preferences={},
            theme="light",
            language="en",
            notification_email=True,
            notification_web=True,
            timezone="UTC",
        )

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
        db.refresh(user)
        db.refresh(settings)

        role = db.query(RoleDB).filter(RoleDB.id == user.role_id).first()

        return UserDetailResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            role=role.name if role else "unknown",
            role_id=user.role_id,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            settings=UserSettingsResponse(
                preferences=settings.preferences,
                theme=settings.theme,
                language=settings.language,
                notification_email=settings.notification_email,
                notification_web=settings.notification_web,
                timezone=settings.timezone,
            ),
        )
