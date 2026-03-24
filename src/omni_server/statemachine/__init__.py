"""StateMachine engine for controlled state transitions with EventSourcing."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Tuple, List, Callable, Optional, Tuple as TypingTuple
from dataclasses import dataclass

from omni_server.statemachine.models import StateTransition
from omni_server.tracing.decorators import async_traced
from omni_server.utils.logging import get_logger

logger = get_logger()

logger = get_logger()


class InvalidStateTransitionError(Exception):
    """Raised when attempting an invalid state transition."""

    pass


@dataclass
class StateMachine:
    """Central state machine for managing state transitions with EventSourcing support."""

    _current_state: Any
    _transitions: Dict[Tuple[Any, Any], StateTransition]
    _listeners: List[Callable[[Any, Any], None]]
    _event_store: Any  # Late binding to avoid circular import

    def __init__(
        self,
        initial_state: Any,
        entity_type: str = "general",
        entity_id: str = "unknown",
        event_store: Optional[Any] = None,
    ):
        """Initialize state machine with initial state and optional event store."""
        self._current_state = initial_state
        self._transitions: Dict[Tuple[Any, Any], StateTransition] = {}
        self._listeners: List[Callable[[Any, Any], None]] = []
        self._entity_type = entity_type
        self._entity_id = entity_id
        self._event_store = event_store  # Optional EventStore for EventSourcing

    def add_transition(self, transition: StateTransition) -> None:
        """Add a state transition rule."""
        key = (transition.from_state, transition.to_state)
        self._transitions[key] = transition

    def can_transition(self, to_state: Any, **kwargs) -> bool:
        """Check if transition to target state is possible."""
        from_state = self._current_state
        key = (from_state, to_state)

        if key not in self._transitions:
            return False

        transition = self._transitions[key]
        return transition.can_execute(**kwargs)

    @async_traced("statemachine.transition")
    async def transition(self, to_state: Any, **kwargs) -> bool:
        """Execute state transition with validation, notifications, and EventSourcing."""
        if not self.can_transition(to_state, **kwargs):
            error_msg = f"Cannot transition from {self._current_state} to {to_state}"
            if self._entity_id != "unknown":
                error_msg += f" for {self._entity_type}:{self._entity_id}"
            raise InvalidStateTransitionError(error_msg)

        from asyncio import get_running_loop

        loop = get_running_loop()
        from_state = self._current_state
        key = (from_state, to_state)
        transition = self._transitions[key]
        event_data = kwargs.get("event_data", {})

        if transition.action:
            try:
                result = transition.action(**kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.bind(
                    entity_type=self._entity_type,
                    entity_id=self._entity_id,
                    from_state=str(from_state),
                    to_state=str(to_state),
                    error=str(e),
                ).error("State transition action failed", exc_info=e)
                raise

        log_context = {
            "entity_type": self._entity_type,
            "entity_id": self._entity_id,
            "from_state": str(from_state),
            "to_state": str(to_state),
            **kwargs,
        }

        logger.bind(**log_context).info(f"State transition: {from_state} → {to_state}")

        self._current_state = to_state

        for listener in self._listeners:
            try:
                listener(from_state, to_state)
            except Exception as e:
                logger.error(f"State listener failed: {e}")

        # Save event to EventStore if available
        if self._event_store:
            try:
                self._event_store.save_event(
                    entity_type=self._entity_type,
                    entity_id=self._entity_id,
                    event_type=f"{self._entity_type}.state_changed",
                    event_data=event_data,
                    from_state=str(from_state),
                    to_state=str(to_state),
                    correlation_id=kwargs.get("correlation_id"),
                )
                logger.debug(
                    f"Saved state transition event to EventStore for {self._entity_type}:{self._entity_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to save event to EventStore: {e}")

        return True

    def get_current_state(self) -> Any:
        """Get current state."""
        return self._current_state

    def get_possible_transitions(self, **kwargs) -> List[Any]:
        """Get list of states that can be transitioned to from current state."""
        possible_states = []
        for (from_state, to_state), transition in self._transitions.items():
            if from_state == self._current_state:
                try:
                    if transition.can_execute(**kwargs):
                        possible_states.append(to_state)
                except Exception:
                    pass

        return possible_states

    def add_listener(self, listener: Callable[[Any, Any], None]) -> None:
        """Add state change listener callback."""
        self._listeners.append(listener)

    def add_transitions_map(self, transitions_map: Dict[Any, List[Any]]) -> None:
        """Bulk add transitions from state => [next_states] mapping."""
        for from_state, to_states in transitions_map.items():
            for to_state in to_states:
                self.add_transition(StateTransition(from_state=from_state, to_state=to_state))


class StateMachineFactory:
    """Factory for creating state machines for different entity types."""

    @staticmethod
    def create_task_state_machine(task_id: str, event_store: Optional[Any] = None) -> StateMachine:
        """Create StateMachine for task state management with EventSourcing support."""
        task_states = {
            TaskState.PENDING: [TaskState.ASSIGNED],
            TaskState.ASSIGNED: [TaskState.RUNNING],
            TaskState.RUNNING: [
                TaskState.SUCCESS,
                TaskState.FAILED,
                TaskState.TIMEOUT,
                TaskState.CRASHED,
            ],
            TaskState.SUCCESS: [],
            TaskState.FAILED: [],
            TaskState.TIMEOUT: [],
            TaskState.CRASHED: [],
            TaskState.SKIPPED: [],
        }

        sm = StateMachine(
            TaskState.PENDING,
            entity_type="task",
            entity_id=task_id,
            event_store=event_store,
        )
        sm.add_transitions_map(task_states)

        return sm

    @staticmethod
    def create_device_state_machine(
        device_id: str, event_store: Optional[Any] = None
    ) -> StateMachine:
        """Create StateMachine for device state management with EventSourcing support."""
        device_states = {
            DeviceState.IDLE: [DeviceState.RUNNING, DeviceState.OFFLINE, DeviceState.MAINTENANCE],
            DeviceState.RUNNING: [DeviceState.IDLE, DeviceState.OFFLINE],
            DeviceState.OFFLINE: [DeviceState.IDLE],
            DeviceState.MAINTENANCE: [DeviceState.IDLE],
        }

        sm = StateMachine(
            DeviceState.IDLE,
            entity_type="device",
            entity_id=device_id,
            event_store=event_store,
        )
        sm.add_transitions_map(device_states)

        return sm


class TaskState(str):
    """Task lifecycle states."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CRASHED = "crashed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class DeviceState(str):
    """Device operational states."""

    IDLE = "idle"
    RUNNING = "running"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


__all__ = [
    "StateMachine",
    "StateMachineFactory",
    "InvalidStateTransitionError",
    "TaskState",
    "DeviceState",
]
