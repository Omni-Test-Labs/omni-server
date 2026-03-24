"""GraphQL API with Query, Mutation, and Subscription support."""

import asyncio
import logging
from typing import Any, AsyncGenerator

import strawberry
from strawberry.types import Info
from sqlalchemy.orm import Session

from omni_server.database import get_db
from omni_server.models import TaskQueueDB, DeviceDB
from omni_server.queue import TaskQueueManager
from omni_server.statemachine import TaskState, DeviceState

logger = logging.getLogger(__name__)


# Strawberry types
@strawberry.type
class Task:
    id: strawberry.ID
    task_id: str
    status: str
    priority: str
    assigned_device_id: str | None
    created_at: str
    updated_at: str
    result: dict[str, Any] | None
    device_binding: dict[str, Any]
    task_manifest: dict[str, Any]

    @classmethod
    def from_db(cls, task_db: TaskQueueDB) -> "Task":
        return cls(
            id=str(task_db.id),
            task_id=task_db.task_id,
            status=task_db.status,
            priority=task_db.priority,
            assigned_device_id=task_db.assigned_device_id,
            created_at=task_db.created_at.isoformat(),
            updated_at=task_db.updated_at.isoformat(),
            result=task_db.result,
            device_binding=task_db.device_binding,
            task_manifest=task_db.task_manifest,
        )


@strawberry.type
class Device:
    id: strawberry.ID
    device_id: str
    name: str
    device_type: str
    status: str
    capabilities: dict[str, Any]
    config: dict[str, Any]
    last_heartbeat_at: str | None
    runner_version: str

    @classmethod
    def from_db(cls, device_db: DeviceDB) -> "Device":
        return cls(
            id=str(device_db.id),
            device_id=device_db.device_id,
            name=device_db.name,
            device_type=device_db.device_type,
            status=device_db.status,
            capabilities=device_db.capabilities,
            config=device_db.config,
            last_heartbeat_at=device_db.last_heartbeat_at.isoformat()
            if device_db.last_heartbeat_at
            else None,
            runner_version=device_db.runner_version,
        )


@strawberry.input
class TaskInput:
    task_id: str
    device_binding: dict[str, Any]
    priority: str
    timeout_seconds: int
    pipeline: list[dict[str, Any]]


@strawberry.type
class TaskResponse:
    success: bool
    message: str
    task: Task | None
    error: str | None


@strawberry.type
class TaskEvent:
    event_type: str
    task_id: str
    status: str
    timestamp: str
    data: dict[str, Any] | None


# Query resolvers
@strawberry.type
class Query:
    @strawberry.field
    def tasks(
        self,
        info: Info[Session, None],
        status: str | None = None,
        limit: int = 100,
    ) -> list[Task]:
        """Get list of tasks optionally filtered by status."""
        tasks_db = TaskQueueManager.list_tasks(info, status=status, limit=limit)
        return [Task.from_db(t) for t in tasks_db]

    @strawberry.field
    def task(self, info: Info[Session, None], task_id: str) -> Task | None:
        """Get a specific task by ID."""
        task_db = TaskQueueManager.get_task_by_id(info, task_id)
        if not task_db:
            return None
        return Task.from_db(task_db)

    @strawberry.field
    def devices(
        self,
        info: Info[Session, None],
        status: str | None = None,
        limit: int = 100,
    ) -> list[Device]:
        """Get list of devices optionally filtered by status."""
        query = info.query(DeviceDB)
        if status:
            query = query.filter(DeviceDB.status == status)
        devices = query.limit(limit).all()
        return [Device.from_db(d) for d in devices]

    @strawberry.field
    def device(self, info: Info[Session, None], device_id: str) -> Device | None:
        """Get a specific device by ID."""
        device_db = info.query(DeviceDB).filter(DeviceDB.device_id == device_id).first()
        if not device_db:
            return None
        return Device.from_db(device_db)


# Mutation resolvers
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_task(self, info: Info[Session, None], task: TaskInput) -> TaskResponse:
        """Create a new task."""
        from omni_server.models import TaskManifest

        try:
            db = info  # Session is passed as Info.info
            manifest = TaskManifest(
                schema_version="1.0.0",
                task_id=task.task_id,
                created_at="",
                device_binding=task.device_binding,
                priority=task.priority,
                timeout_seconds=task.timeout_seconds,
                pipeline=task.pipeline,
            )
            TaskQueueManager.enqueue_task(
                db=db,
                task_id=task.task_id,
                device_binding=task.device_binding,
                task_manifest=manifest.model_dump(),
            )

            db_task = TaskQueueManager.get_task_by_id(db, task.task_id)
            return TaskResponse(
                success=True,
                message="Task created successfully",
                task=Task.from_db(db_task),
                error=None,
            )
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return TaskResponse(
                success=False,
                message=f"Failed to create task: {str(e)}",
                task=None,
                error=str(e),
            )


# Subscription resolvers
@strawberry.type
class Subscription:
    @strawberry.subscription
    async def task_events(
        self, info: Info[Session, None], task_id: str | None = None
    ) -> AsyncGenerator[TaskEvent, None]:
        """Subscribe to task events, optionally filtered by task_id."""
        from omni_server.events import get_event_bus

        event_bus = get_event_bus()
        channel = f"tasks:{task_id}" if task_id else "tasks"
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Register subscription queue with event bus
        await event_bus.subscribe_queue(channel, queue)

        try:
            while True:
                event = await queue.get()
                yield TaskEvent(
                    event_type=event["message"].get("event_type", "unknown"),
                    task_id=event["message"].get("task_id", ""),
                    status=event["message"].get("status", ""),
                    timestamp=event["timestamp"],
                    data=event["message"].get("data"),
                )
        except asyncio.CancelledError:
            # Cleanup on cancellation
            event_bus.unsubscribe_queue(channel, queue)
            raise


# Create Strawberry schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)

__all__ = ["schema"]
