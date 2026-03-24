"""API version configuration and management."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Any


class Version(str, Enum):
    """API version enum."""

    V1 = "v1"
    V2 = "v2"
    V3 = "v3"
    LATEST = "v3"


@dataclass
class DeprecationInfo:
    """Information about a deprecated API version."""

    deprecated_since: datetime
    sunset_date: datetime
    migration_target: Version
    warning_message: str
    is_deprecated: bool = False

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.sunset_date

    def days_until_sunset(self) -> int:
        delta = self.sunset_date - datetime.utcnow()
        return delta.days if delta.days > 0 else 0


@dataclass
class VersionConfig:
    """Configuration for an API version."""

    version: Version
    release_date: datetime
    stable: bool = True
    breaking_changes: list[str] = None
    new_features: list[str] = None
    deprecation_info: Optional[DeprecationInfo] = None

    def __post_init__(self):
        if self.breaking_changes is None:
            self.breaking_changes = []
        if self.new_features is None:
            self.new_features = []


class VersionRegistry:
    """Registry for managing API versions."""

    def __init__(self):
        self._versions: dict[Version, VersionConfig] = {}
        _configure_defaults(self)

    def get_config(self, version: Version) -> Optional[VersionConfig]:
        """Get configuration for a version."""
        return self._versions.get(version)

    def get_latest_version(self) -> Version:
        """Get the latest stable version."""
        return max((v for v, cfg in self._versions.items() if cfg.stable), default=Version.V3)

    def get_deprecated_versions(self) -> list[Version]:
        """Get list of deprecated versions."""
        return [
            v
            for v, cfg in self._versions.items()
            if cfg.deprecation_info and cfg.deprecation_info.is_deprecated
        ]

    def is_supported(self, version: Version) -> bool:
        """Check if a version is supported (not sunset)."""
        cfg = self.get_config(version)
        if not cfg:
            return False

        if cfg.deprecation_info:
            return not cfg.deprecation_info.is_expired()

        return True

    def get_sunset_warning(self, version: Version) -> Optional[str]:
        """Get sunset warning message for a version."""
        cfg = self.get_config(version)
        if not cfg or not cfg.deprecation_info or not cfg.deprecation_info.is_deprecated:
            return None

        deprecation = cfg.deprecation_info
        days_left = deprecation.days_until_sunset()
        target = deprecation.migration_target.value

        return (
            f"API version {version} is deprecated and will be sunset in {days_left} days. "
            f"Please migrate to {target}. {deprecation.warning_message}"
        )


def _configure_defaults(registry: VersionRegistry) -> None:
    """Configure default API versions."""
    now = datetime.utcnow()

    registry._versions[Version.V1] = VersionConfig(
        version=Version.V1,
        release_date=now - timedelta(days=365),
        stable=True,
        breaking_changes=[],
        new_features=["Initial release"],
        deprecation_info=DeprecationInfo(
            deprecated_since=now - timedelta(days=180),
            sunset_date=now + timedelta(days=90),
            migration_target=Version.V2,
            warning_message="v1 will be removed in 90 days. Please migrate to v2 or v3.",
            is_deprecated=True,
        ),
    )

    registry._versions[Version.V2] = VersionConfig(
        version=Version.V2,
        release_date=now - timedelta(days=180),
        stable=True,
        breaking_changes=["Updated response format for /api/v1/tasks endpoint"],
        new_features=["Enhanced filtering", "Batch operations"],
    )

    registry._versions[Version.V3] = VersionConfig(
        version=Version.V3,
        release_date=now - timedelta(days=30),
        stable=True,
        breaking_changes=["Deprecated legacy authentication"],
        new_features=["GraphQL support", "Advanced event streaming", "Real-time subscriptions"],
    )


_global_registry: Optional[VersionRegistry] = None


def get_registry() -> VersionRegistry:
    """Get global version registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = VersionRegistry()
    return _global_registry


__all__ = ["Version", "DeprecationInfo", "VersionConfig", "VersionRegistry", "get_registry"]
