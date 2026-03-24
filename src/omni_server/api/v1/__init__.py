"""API package initialization for version 1."""

from fastapi import APIRouter
from omni_server.api.v1 import tasks, devices, dependencies, websocket, observability, eventsourcing

router = APIRouter(prefix="", tags=["api-v1"])

router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(dependencies.router, prefix="", tags=["dependencies", "locks"])
router.include_router(devices.router, prefix="/devices", tags=["devices"])
router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
router.include_router(observability.router, prefix="/observability", tags=["observability"])
router.include_router(eventsourcing.router, prefix="/eventsourcing", tags=["eventsourcing"])

__all__ = ["router"]
