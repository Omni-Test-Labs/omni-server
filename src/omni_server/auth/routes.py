"""Authentication routes for registration, login, and OAuth."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..config import Settings
from ..database import get_db
from ..models import UserDB
from .models import (
    TokenRefreshRequest,
    TokenResponse,
    UserDetailResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserUpdateRequest,
)
from .service import AuthService

router = APIRouter(prefix="/api/auth", tags=["authentication"])
oauth2_scheme = HTTPBearer(auto_error=False)

# Initialize settings
settings = Settings()
auth_service = AuthService(settings)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> UserDB:
    """Dependency to get current authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return auth_service.get_current_user(db, credentials.credentials)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserRegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Register a new user account."""
    return auth_service.register_user(db, user_data)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    login_data: UserLoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    return auth_service.login_user(db, login_data)


@router.get("/oauth/github")
def github_oauth_redirect(request_url: str | None = None) -> dict:
    """Redirect user to GitHub OAuth page."""
    import urllib.parse

    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": "user:email",
        "state": "state_token",
    }
    oauth_url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
    return {"redirect_url": oauth_url}


@router.get("/oauth/github/callback", response_model=TokenResponse)
async def github_oauth_callback(
    code: str,
    state: str,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Handle GitHub OAuth callback."""
    # Validate state for CSRF protection
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )

    return await auth_service.handle_github_oauth(db, code)


@router.get("/oauth/gitlab")
def gitlab_oauth_redirect(request_url: str | None = None) -> dict:
    """Redirect user to GitLab OAuth page."""
    import urllib.parse

    params = {
        "client_id": settings.gitlab_client_id,
        "redirect_uri": settings.gitlab_redirect_uri,
        "scope": "read_user",
        "response_type": "code",
        "state": "state_token",
    }
    oauth_url = f"https://gitlab.com/oauth/authorize?{urllib.parse.urlencode(params)}"
    return {"redirect_url": oauth_url}


@router.get("/oauth/gitlab/callback", response_model=TokenResponse)
async def gitlab_oauth_callback(
    code: str,
    state: str,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Handle GitLab OAuth callback."""
    # Validate state for CSRF protection
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )

    return await auth_service.handle_gitlab_oauth(db, code)


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh(
    refresh_data: TokenRefreshRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Refresh access token using refresh token."""
    return await auth_service.refresh_tokens(db, refresh_data.refresh_token)


@router.get("/me", response_model=UserDetailResponse, status_code=status.HTTP_200_OK)
def get_current_user_info(
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserDetailResponse:
    """Get current user profile."""
    return auth_service.get_user_by_id(db, current_user.id)


@router.patch("/me", response_model=UserDetailResponse, status_code=status.HTTP_200_OK)
def update_current_user_info(
    update_data: UserUpdateRequest,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserDetailResponse:
    """Update current user profile."""
    return auth_service.update_user(db, current_user.id, update_data)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: Annotated[UserDB, Depends(get_current_user)],
) -> None:
    """Logout current user (client-side token deletion)."""
    # JWT tokens are stateless, so no server-side logout needed
    # Client should delete the tokens from storage
    return None
