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
    heartbeat_timeout_seconds: int = 300
    heartbeat_retention_days: int = 7
    heartbeat_cleanup_enabled: bool = True

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

    # OAuth Configuration (Development use localhost:5173 for frontend callback)
    # For production, replace with your public domain
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:5173/auth/github/callback"
    gitlab_client_id: str = ""
    gitlab_client_secret: str = ""
    gitlab_redirect_uri: str = "http://localhost:5173/auth/gitlab/callback"

    # AI RCA Configuration
    rca_enabled: bool = False
    auto_rca_on_failure: bool = False
    llm_provider: str = "openai"  # openai, anthropic, ollama
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = ""  # For alternative providers
    llm_fallback_provider: str = "anthropic"
    llm_fallback_model: str = "claude-3-5-sonnet-20241022"
    llm_fallback_api_key: str = ""
    rca_system_prompt: str = ""
    max_rca_per_hour: int = 100
    rca_cache_ttl_seconds: int = 86400  # 24 hours
    max_tokens_per_request: int = 4000
    enable_rca_cache: bool = True
