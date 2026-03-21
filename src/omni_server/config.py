"""Server configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    app_name: str = "omni-server"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite:///./omni.db"

    # Task Queue
    task_retention_seconds: int = 604800  # 7 days
    max_pending_tasks_per_device: int = 10

    # Heartbeats
    heartbeat_timeout_seconds: int = 300  # 5 minutes

    # JWT Authentication
    jwt_secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    _access_token_expire_minutes: int = 30
    _refresh_token_expire_days: int = 7

    @property
    def access_token_expire_minutes(self) -> int:
        """Get access token expiration in minutes."""
        return self._access_token_expire_minutes

    @property
    def refresh_token_expire_days(self) -> int:
        """Get refresh token expiration in days."""
        return self._refresh_token_expire_days

    # OAuth Configuration
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:3000/auth/github/callback"
    gitlab_client_id: str = ""
    gitlab_client_secret: str = ""
    gitlab_redirect_uri: str = "http://localhost:3000/auth/gitlab/callback"
