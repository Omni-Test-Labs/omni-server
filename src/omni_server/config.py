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
