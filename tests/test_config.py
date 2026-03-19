"""Tests for server configuration."""

import os
from pathlib import Path

import pytest

from omni_server.config import Settings


class TestSettingsDefaults:
    """Test Settings default values."""

    def test_default_server_settings(self):
        """Test default server configuration."""
        settings = Settings()
        assert settings.app_name == "omni-server"
        assert settings.debug is False
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000

    def test_default_database_settings(self):
        """Test default database configuration."""
        settings = Settings()
        assert settings.database_url == "sqlite:///./omni.db"

    def test_default_task_queue_settings(self):
        """Test default task queue configuration."""
        settings = Settings()
        assert settings.task_retention_seconds == 604800  # 7 days
        assert settings.max_pending_tasks_per_device == 10

    def test_default_heartbeat_settings(self):
        """Test default heartbeat configuration."""
        settings = Settings()
        assert settings.heartbeat_timeout_seconds == 300  # 5 minutes


class TestSettingsOverride:
    """Test Settings with environment variable overrides."""

    def test_override_with_env_var(self, monkeypatch: pytest.MonkeyPatch):
        """Test overriding settings with environment variables."""
        monkeypatch.setenv("APP_NAME", "custom-server")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        settings = Settings()
        assert settings.app_name == "custom-server"
        assert settings.debug is True
        assert settings.port == 9000
        assert settings.database_url == "postgresql://localhost/test"

    def test_case_insensitive_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Test that environment variables are case-insensitive."""
        monkeypatch.setenv("DEBUG", "TRUE")
        monkeypatch.setenv("PORT", "8080")

        settings = Settings()
        assert settings.debug is True
        assert settings.port == 8080

    def test_model_config_ignore_extra(self):
        """Test that extra environment variables are ignored."""
        settings = Settings(
            app_name="test",
            unknown_field="should_not_cause_error",  # type: ignore
            debug=False,  # type: ignore
        )
        assert settings.app_name == "test"
        assert not hasattr(settings, "unknown_field")


class TestSettingsValidation:
    """Test Settings validation."""

    def test_port_is_integer(self):
        """Test that port is validated as integer."""
        settings = Settings(port=8080)
        assert settings.port == 8080
        assert isinstance(settings.port, int)

    def test_debug_is_boolean(self):
        """Test that debug is validated as boolean."""
        settings = Settings(debug=True)
        assert settings.debug is True
        assert isinstance(settings.debug, bool)

    def test_database_url_is_string(self):
        """Test that database_url is validated as string."""
        settings = Settings(database_url="sqlite:///:memory:")
        assert settings.database_url == "sqlite:///:memory:"
        assert isinstance(settings.database_url, str)
