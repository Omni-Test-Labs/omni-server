"""Event bus for real-time event distribution."""

from .events import TaskEvent, DeviceEvent, AgentEvent

__all__ = ["EventBus", "get_event_bus", "TaskEvent", "DeviceEvent", "AgentEvent"]

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class EventBus:
    """Central event bus for real-time event distribution."""

    def __init__(self):
        self.clients: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True

    async def stop(self):
        self._running = False

    async def connect(self, channel: str, websocket: WebSocket):
        await websocket.accept()
        self.clients[channel].add(websocket)

    async def disconnect(self, channel: str, websocket: WebSocket):
        if channel in self.clients:
            self.clients[channel].discard(websocket)

    async def publish(self, channel: str, message: dict[str, Any]):
        event = {
            "channel": channel,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.message_queue.put(event)

        if channel in self.clients:
            disconnected = []
            for ws in self.clients[channel]:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)

            for ws in disconnected:
                await self.disconnect(channel, ws)

    async def subscribe(
        self,
        channel: str,
        websocket: WebSocket,
        since: Optional[datetime] = None,
    ):
        await self.connect(channel, websocket)

        # Historical events not yet implemented - for future enhancement
        if since:
            logger.info(f"Historical events requested since {since}, but not yet implemented")

        try:
            while self._running:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "keepalive"})
                except Exception:
                    break
        except WebSocketDisconnect:
            pass
        finally:
            await self.disconnect(channel, websocket)

    async def get_history(self, channel: str, since: datetime) -> List[dict]:
        """Get historical events - not yet implemented."""
        return []


_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus
