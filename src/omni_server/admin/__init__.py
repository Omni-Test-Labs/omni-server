"""Admin module for user, device, task, and application management."""

from .users.routes import router as users_router

__all__ = ["users_router"]
