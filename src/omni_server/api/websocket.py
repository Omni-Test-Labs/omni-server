"""WebSocket endpoints for real-time event streaming."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket

from omni_server.events import get_event_bus
from omni_server.database import SessionLocal
from omni_server.auth import AuthService
from omni_server.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws")

settings = Settings()
auth_service = AuthService(settings)


@router.websocket("/tasks/{task_id}")
async def task_events(
    websocket: WebSocket,
    task_id: str,
    token: Optional[str] = None,
    since: Optional[str] = None,
):
    """WebSocket endpoint for task event streaming."""
    await authenticate_websocket(websocket, token)

    event_bus = get_event_bus()
    since_dt = datetime.fromisoformat(since) if since else None

    await event_bus.subscribe(f"task:{task_id}", websocket, since_dt)


@router.websocket("/devices/{device_id}")
async def device_events(
    websocket: WebSocket,
    device_id: str,
    token: Optional[str] = None,
    since: Optional[str] = None,
):
    """WebSocket endpoint for device event streaming."""
    await authenticate_websocket(websocket, token)

    event_bus = get_event_bus()
    since_dt = datetime.fromisoformat(since) if since else None

    await event_bus.subscribe(f"device:{device_id}", websocket, since_dt)


@router.websocket("/agent/{agent_id}")
async def agent_events(
    websocket: WebSocket,
    agent_id: str,
    token: Optional[str] = None,
    since: Optional[str] = None,
):
    """WebSocket endpoint for agent event streaming."""
    await authenticate_websocket(websocket, token)

    event_bus = get_event_bus()
    since_dt = datetime.fromisoformat(since) if since else None

    await event_bus.subscribe(f"agent:{agent_id}", websocket, since_dt)


async def authenticate_websocket(websocket: WebSocket, token: Optional[str]) -> None:
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    db = SessionLocal()
    try:
        auth_service.get_current_user(db, token)
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="Invalid authentication token")
    finally:
        db.close()
