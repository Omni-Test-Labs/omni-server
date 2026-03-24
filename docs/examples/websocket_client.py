"""WebSocket client example for omni-server real-time events."""

import asyncio
import json
from typing import Any, Callable

import websockets
from websockets.exceptions import ConnectionClosed


class WSClient:
    """Simple WebSocket client for omni-server events."""

    def __init__(self, base_url: str = "ws://localhost:8000", token: str | None = None):
        self.base_url = base_url
        self.token = token

    async def subscribe_to_task(
        self,
        task_id: str,
        on_message: Callable[[dict[str, Any]], Any],
        since: str | None = None,
    ):
        """Subscribe to task events."""
        url = f"{self.base_url}/api/v1/ws/tasks/{task_id}"
        await self._subscribe(url, on_message, since)

    async def subscribe_to_device(
        self,
        device_id: str,
        on_message: Callable[[dict[str, Any]], Any],
        since: str | None = None,
    ):
        """Subscribe to device events."""
        url = f"{self.base_url}/api/v1/ws/devices/{device_id}"
        await self._subscribe(url, on_message, since)

    async def subscribe_to_agent(
        self,
        agent_id: str,
        on_message: Callable[[dict[str, Any]], Any],
        since: str | None = None,
    ):
        """Subscribe to agent events."""
        url = f"{self.base_url}/api/v1/ws/agent/{agent_id}"
        await self._subscribe(url, on_message, since)

    async def _subscribe(
        self,
        url: str,
        on_message: Callable[[dict[str, Any]], Any],
        since: str | None = None,
    ):
        """Subscribe to WebSocket events."""
        if since:
            url += f"?since={since}"
        if self.token:
            url += f"&token={self.token}" if since else f"?token={self.token}"

        async with websockets.connect(url) as websocket:
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    await on_message(data)
                except ConnectionClosed:
                    break
                except json.JSONDecodeError as e:
                    print(f"Invalid JSON received: {e}")


async def main():
    """Example usage."""

    def on_message(data: dict[str, Any]):
        """Handle incoming WebSocket message."""
        event_type = data.get("event_type", "unknown")
        print(f"[{event_type}] {json.dumps(data, indent=2)}")

    client = WSClient(base_url="ws://localhost:8000")

    print("Subscribing to task events...")
    await client.subscribe_to_task(
        task_id="example-task-123",
        on_message=on_message,
    )


if __name__ == "__main__":
    print("WebSocket Client Example")
    print("=" * 50)
    print("Install dependencies:")
    print("  pip install websockets")
    print("=" * 50)
    asyncio.run(main())
