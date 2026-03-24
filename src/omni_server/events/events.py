"""Event schemas for real-time event distribution."""

from typing import Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class BaseEvent(BaseModel):
    """Base event structure."""

    event_type: str = Field(..., description="Type of event")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: dict[str, Any] = Field(default_factory=dict)


class TaskEvent(BaseModel):
    """Task-related event."""

    event_type: str = Field(
        ...,
        description="Type: task.created, task.assigned, task.started, task.completed, task.failed",
    )
    task_id: str
    device_id: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class DeviceEvent(BaseModel):
    """Device-related event."""

    event_type: str = Field(
        ..., description="Type: device.registered, device.online, device.offline, device.heartbeat"
    )
    device_id: str
    status: Optional[str] = None
    runner_version: Optional[str] = None
    capabilities: Optional[dict[str, Any]] = None
    details: dict[str, Any] = Field(default_factory=dict)


class AgentEvent(BaseModel):
    """Agent-related event."""

    event_type: str = Field(..., description="Type: agent.started, agent.stopped, agent.status")
    agent_id: str
    status: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)
