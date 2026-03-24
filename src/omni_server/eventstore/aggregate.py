"""AggregateRoot base class and implementations for EventSourcing."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar

from sqlalchemy.orm import Session

from omni_server.eventstore import EventStore
from omni_server.models import StateEventDB, TaskQueueDB, DeviceDB
from omni_server.statemachine import StateMachine, TaskState, DeviceState

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="AggregateRoot")


class AggregateRoot(ABC):
    """Base class for aggregates in EventSourcing pattern."""

    def __init__(self, entity_type: str, entity_id: str, event_store: EventStore):
        """Initialize aggregate root."""
        self._entity_type = entity_type
        self._entity_id = entity_id
        self._event_store = event_store
        self._version = 0
        self._uncommitted_events: List[Dict[str, Any]] = []
        self._state: Any = None

    @property
    def entity_type(self) -> str:
        """Get entity type."""
        return self._entity_type

    @property
    def entity_id(self) -> str:
        """Get entity ID."""
        return self._entity_id

    @property
    def version(self) -> int:
        """Get current version."""
        return self._version

    @property
    def state(self) -> Any:
        """Get current state."""
        return self._state

    def load_from_history(self) -> None:
        """Rebuild aggregate state from event history."""
        events = self._event_store.get_events(self._entity_type, self._entity_id)
        for event in events:
            self._apply_event(event)
            self._version = event.version

    def save_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        causation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> StateEventDB:
        """Save a new event to the event store."""
        event = self._event_store.save_event(
            entity_type=self._entity_type,
            entity_id=self._entity_id,
            event_type=event_type,
            event_data=event_data,
            from_state=from_state,
            to_state=to_state,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )

        self._version = event.version
        self._uncommitted_events.append(event_data)

        return event

    def get_history(self, limit: Optional[int] = None) -> List[StateEventDB]:
        """Get event history for this aggregate."""
        return self._event_store.get_events(self._entity_type, self._entity_id, limit=limit)

    def get_events_for_version(self, version: int) -> List[StateEventDB]:
        """Get all events up to a specific version."""
        events = self.get_history()
        return [e for e in events if e.version <= version]

    @abstractmethod
    def _apply_event(self, event: StateEventDB) -> None:
        """Apply an event to update aggregate state."""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert aggregate state to dictionary."""
        pass

    @classmethod
    @abstractmethod
    def create_new(cls: type[T], db: Session, **kwargs: Any) -> T:
        """Create a new aggregate and save initial event."""
        pass

    @classmethod
    @abstractmethod
    def load(cls: type[T], db: Session, entity_id: str) -> Optional[T]:
        """Load an aggregate from event store."""
        pass


class TaskAggregate(AggregateRoot):
    """Aggregate for task entities with state machine integration."""

    def __init__(self, task_id: str, event_store: EventStore, task_manifest: Optional[Dict] = None):
        """Initialize TaskAggregate."""
        super().__init__("task", task_id, event_store)
        self._task_manifest = task_manifest
        self._current_state = TaskState.PENDING if task_manifest else None
        self._assigned_device_id: Optional[str] = None
        self._result: Optional[Dict] = None
        self._created_at: Optional[datetime] = None

    def _apply_event(self, event: StateEventDB) -> None:
        """Apply event to update task state."""
        if event.event_type == "task.created":
            self._current_state = TaskState.PENDING
            self._created_at = event.timestamp
            self._task_manifest = event.event_data.get("task_manifest", {})
            self._assigned_device_id = None
            self._result = None

        elif event.event_type == "task.assigned":
            self._current_state = TaskState.ASSIGNED
            self._assigned_device_id = event.event_data.get("device_id")

        elif event.event_type == "task_started":
            self._current_state = TaskState.RUNNING

        elif event.event_type == "task.completed":
            self._current_state = TaskState.SUCCESS
            self._result = event.event_data.get("result")

        elif event.event_type == "task.failed":
            self._current_state = TaskState.FAILED
            self._result = event.event_data.get("result")

        elif event.event_type == "task.cancelled":
            self._current_state = TaskState.SKIPPED

        elif event.to_state:
            self._current_state = TaskState(event.to_state)

    def transition_state(
        self,
        to_state: TaskState,
        event_data: Optional[Dict] = None,
        state_machine: Optional[StateMachine] = None,
    ) -> StateEventDB:
        """Transition task state and record event."""
        from_state = self._current_state.value if self._current_state else None

        if state_machine:
            if not state_machine.can_transition(to_state):
                raise ValueError(f"Invalid state transition from {from_state} to {to_state}")
            await_state_machine = state_machine.transition(to_state)

        event_data = event_data or {}
        event_type = f"task.{to_state.value}" if from_state != to_state else "task.state_changed"

        return self.save_event(
            event_type=event_type,
            event_data=event_data,
            from_state=from_state,
            to_state=to_state.value,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert task aggregate to dictionary."""
        return {
            "task_id": self._entity_id,
            "state": self._current_state.value if self._current_state else None,
            "task_manifest": self._task_manifest,
            "assigned_device_id": self._assigned_device_id,
            "result": self._result,
            "created_at": self._created_at.isoformat() if self._created_at else None,
            "version": self._version,
        }

    @classmethod
    def create_new(
        cls: type["TaskAggregate"], db: Session, task_manifest: Dict[str, Any]
    ) -> "TaskAggregate":
        """Create a new task aggregate with initial event."""
        from omni_server.eventstore import EventStore

        task_id = task_manifest.get("task_id")
        event_store = EventStore(db)

        aggregate = cls(task_id, event_store, task_manifest)
        aggregate.save_event(
            event_type="task.created",
            event_data={"task_manifest": task_manifest},
            from_state=None,
            to_state=TaskState.PENDING.value,
        )

        return aggregate

    @classmethod
    def load(cls: type["TaskAggregate"], db: Session, task_id: str) -> Optional["TaskAggregate"]:
        """Load task aggregate from event store."""
        from omni_server.eventstore import EventStore

        event_store = EventStore(db)
        aggregate = cls(task_id, event_store)
        aggregate.load_from_history()

        if aggregate.version == 0:
            return None

        return aggregate


class DeviceAggregate(AggregateRoot):
    """Aggregate for device entities with state machine integration."""

    def __init__(self, device_id: str, event_store: EventStore, config: Optional[Dict] = None):
        """Initialize DeviceAggregate."""
        super().__init__("device", device_id, event_store)
        self._config = config or {}
        self._current_state = DeviceState.IDLE if config else None
        self._capabilities: Dict = {}
        self._last_heartbeat_at: Optional[datetime] = None

    def _apply_event(self, event: StateEventDB) -> None:
        """Apply event to update device state."""
        if event.event_type == "device.registered":
            self._current_state = DeviceState.OFFLINE
            self._config = event.event_data.get("config", {})
            self._capabilities = event.event_data.get("capabilities", {})

        elif event.event_type == "device.heartbeat":
            self._last_heartbeat_at = event.timestamp
            heartbeat_data = event.event_data.get("heartbeat", {})
            new_state = heartbeat_data.get("status")
            if new_state:
                self._current_state = DeviceState(new_state)
            self._capabilities = heartbeat_data.get("capabilities", self._capabilities)

        elif event.to_state:
            self._current_state = DeviceState(event.to_state)

    def transition_state(
        self,
        to_state: DeviceState,
        event_data: Optional[Dict] = None,
        state_machine: Optional[StateMachine] = None,
    ) -> StateEventDB:
        """Transition device state and record event."""
        from_state = self._current_state.value if self._current_state else None

        event_data = event_data or {}
        event_type = (
            f"device.{to_state.value}" if from_state != to_state else "device.state_changed"
        )

        return self.save_event(
            event_type=event_type,
            event_data=event_data,
            from_state=from_state,
            to_state=to_state.value,
        )

    def record_heartbeat(self, heartbeat_data: Dict[str, Any]) -> StateEventDB:
        """Record device heartbeat as an event."""
        return self.save_event(
            event_type="device.heartbeat",
            event_data={"heartbeat": heartbeat_data},
            to_state=self._current_state.value if self._current_state else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert device aggregate to dictionary."""
        return {
            "device_id": self._entity_id,
            "state": self._current_state.value if self._current_state else None,
            "config": self._config,
            "capabilities": self._capabilities,
            "last_heartbeat_at": self._last_heartbeat_at.isoformat()
            if self._last_heartbeat_at
            else None,
            "version": self._version,
        }

    @classmethod
    def create_new(
        cls: type["DeviceAggregate"], db: Session, config: Dict[str, Any]
    ) -> "DeviceAggregate":
        """Create a new device aggregate with initial event."""
        from omni_server.eventstore import EventStore

        device_id = config.get("device_id")
        event_store = EventStore(db)

        aggregate = cls(device_id, event_store, config)
        aggregate.save_event(
            event_type="device.registered",
            event_data={"config": config, "capabilities": config.get("capabilities", {})},
            from_state=None,
            to_state=DeviceState.OFFLINE.value,
        )

        return aggregate

    @classmethod
    def load(
        cls: type["DeviceAggregate"], db: Session, device_id: str
    ) -> Optional["DeviceAggregate"]:
        """Load device aggregate from event store."""
        from omni_server.eventstore import EventStore

        event_store = EventStore(db)
        aggregate = cls(device_id, event_store)
        aggregate.load_from_history()

        if aggregate.version == 0:
            return None

        return aggregate


__all__ = [
    "AggregateRoot",
    "TaskAggregate",
    "DeviceAggregate",
]
