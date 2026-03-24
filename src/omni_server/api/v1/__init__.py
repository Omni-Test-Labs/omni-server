"""API package initialization for version 1."""

from fastapi import APIRouter
from omni_server.api import tasks, devices, dependencies, websocket, observability, eventsourcing

router = APIRouter(prefix="", tags=["api-v1"])

router.include_router(tasks.router)
router.include_router(dependencies.router)
router.include_router(devices.router)
router.include_router(websocket.router)
router.include_router(observability.router)
router.include_router(eventsourcing.router)

__all__ = ["router"]
