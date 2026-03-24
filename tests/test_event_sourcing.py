"""Tests for EventSourcing implementation."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import desc

from omni_server.models import StateEventDB
from omni_server.eventstore import EventStore
from omni_server.eventstore.aggregate import TaskAggregate, DeviceAggregate, AggregateRoot
from omni_server.statemachine import TaskState, DeviceState, StateMachineFactory


class TestEventStore:
    """Test EventStore class methods."""

    def test_save_event_creates_record(self, db):
        """Test that save_event creates a database record."""
        event_store = EventStore(db)

        event = event_store.save_event(
            entity_type="task",
            entity_id="task-001",
            event_type="task.created",
            event_data={"task_id": "task-001", "message": "Task created"},
            from_state=None,
            to_state="pending",
        )

        assert event.id is not None
        assert event.entity_type == "task"
        assert event.entity_id == "task-001"
        assert event.event_type == "task.created"
        assert event.from_state is None
        assert event.to_state == "pending"
        assert event.version == 1

    def test_save_event_increments_version(self, db):
        """Test that event version increments for each event."""
        event_store = EventStore(db)

        event_store.save_event(
            entity_type="task",
            entity_id="task-001",
            event_type="task.created",
            event_data={},
            to_state="pending",
        )

        event_store.save_event(
            entity_type="task",
            entity_id="task-001",
            event_type="task.assigned",
            event_data={},
            from_state="pending",
            to_state="assigned",
        )

        events = event_store.get_events("task", "task-001")
        assert len(events) == 2
        assert events[0].version == 1
        assert events[1].version == 2

    def test_get_events_returns_ordered_by_version(self, db):
        """Test that get_events returns events ordered by version."""
        event_store = EventStore(db)

        for i in range(5):
            event_store.save_event(
                entity_type="task",
                entity_id="task-001",
                event_type=f"event_{i}",
                event_data={"index": i},
                to_state="pending",
            )

        events = event_store.get_events("task", "task-001")
        assert len(events) == 5
        for i, event in enumerate(events):
            assert event.version == i + 1

    def test_get_events_with_limit(self, db):
        """Test that get_events respects limit parameter."""
        event_store = EventStore(db)

        for i in range(10):
            event_store.save_event(
                entity_type="task",
                entity_id="task-001",
                event_type=f"event_{i}",
                event_data={},
                to_state="pending",
            )

        events = event_store.get_events("task", "task-001", limit=5)
        assert len(events) == 5

    def test_get_events_with_from_version(self, db):
        """Test that get_events respects from_version parameter."""
        event_store = EventStore(db)

        for i in range(10):
            event_store.save_event(
                entity_type="task",
                entity_id="task-001",
                event_type=f"event_{i}",
                event_data={},
                to_state="pending",
            )

        events = event_store.get_events("task", "task-001", from_version=5)
        assert len(events) == 6
        assert events[0].version == 5

    def test_get_event_at_version(self, db):
        """Test retrieving a specific event at a given version."""
        event_store = EventStore(db)

        for i in range(5):
            event_store.save_event(
                entity_type="task",
                entity_id="task-001",
                event_type=f"event_{i}",
                event_data={"version": i},
                to_state="pending",
            )

        event = event_store.get_event_at_version("task", "task-001", 3)
        assert event is not None
        assert event.version == 3
        assert event.event_data["version"] == 2
        assert event.event_type == "event_2"

    def test_get_event_at_version_not_found(self, db):
        """Test retrieving event at non-existent version returns None."""
        event_store = EventStore(db)

        event = event_store.get_event_at_version("task", "task-001", 999)
        assert event is None

    def test_get_events_by_correlation_id(self, db):
        """Test retrieving events by correlation ID."""
        event_store = EventStore(db)
        correlation_id = "corr-123"

        event_store.save_event(
            entity_type="task",
            entity_id="task-001",
            event_type="task.created",
            event_data={},
            correlation_id=correlation_id,
            to_state="pending",
        )

        event_store.save_event(
            entity_type="task",
            entity_id="task-002",
            event_type="task.assigned",
            event_data={},
            correlation_id=correlation_id,
            to_state="assigned",
        )

        event_store.save_event(
            entity_type="task",
            entity_id="task-003",
            event_type="task.created",
            event_data={},
            correlation_id="corr-456",
            to_state="pending",
        )

        events = event_store.get_events_by_correlation_id(correlation_id)
        assert len(events) == 2
        assert all(e.correlation_id == correlation_id for e in events)

    def test_get_events_by_date_range(self, db):
        """Test retrieving events within a date range."""
        event_store = EventStore(db)
        now = datetime.utcnow()

        event_store.save_event(
            entity_type="task",
            entity_id="task-001",
            event_type="task.created",
            event_data={},
            to_state="pending",
        )

        event = event_store.get_events_by_date_range(
            "task",
            from_date=now - timedelta(minutes=1),
            to_date=now + timedelta(minutes=1),
            entity_ids=["task-001"],
        )

        assert len(event) == 1
        assert event[0].entity_id == "task-001"

    def test_replay_events(self, db):
        """Test replaying events through a handler function."""
        event_store = EventStore(db)

        events_data = []
        for i in range(3):
            event_store.save_event(
                entity_type="task",
                entity_id="task-001",
                event_type=f"event_{i}",
                event_data={"index": i},
                to_state="pending",
            )

        def handler(event):
            events_data.append(event.event_data["index"])

        event_store.replay_events("task", "task-001", handler)
        assert events_data == [0, 1, 2]

    def test_replay_events_with_to_version(self, db):
        """Test replaying events up to a specific version."""
        event_store = EventStore(db)

        events_data = []
        for i in range(5):
            event_store.save_event(
                entity_type="task",
                entity_id="task-001",
                event_type=f"event_{i}",
                event_data={"index": i},
                to_state="pending",
            )

        def handler(event):
            events_data.append(event.event_data["index"])

        event_store.replay_events("task", "task-001", handler, to_version=3)
        assert events_data == [0, 1, 2]

    def test_delete_events(self, db):
        """Test deleting events for an entity."""
        event_store = EventStore(db)

        for i in range(5):
            event_store.save_event(
                entity_type="task",
                entity_id="task-001",
                event_type=f"event_{i}",
                event_data={},
                to_state="pending",
            )

        deleted_count = event_store.delete_events("task", "task-001")
        assert deleted_count == 5

        remaining = event_store.get_events("task", "task-001")
        assert len(remaining) == 0

    def test_delete_events_with_before_version(self, db):
        """Test deleting events before a specific version."""
        event_store = EventStore(db)

        for i in range(5):
            event_store.save_event(
                entity_type="task",
                entity_id="task-001",
                event_type=f"event_{i}",
                event_data={},
                to_state="pending",
            )

        deleted_count = event_store.delete_events("task", "task-001", before_version=3)
        assert deleted_count == 2

        remaining = event_store.get_events("task", "task-001")
        assert len(remaining) == 3
        assert remaining[0].version == 3

    def test_get_entity_version(self, db):
        """Test getting the current version of an entity."""
        event_store = EventStore(db)

        version = event_store.get_entity_version("task", "task-001")
        assert version == 0

        event_store.save_event(
            entity_type="task",
            entity_id="task-001",
            event_type="task.created",
            event_data={},
            to_state="pending",
        )

        version = event_store.get_entity_version("task", "task-001")
        assert version == 1


class TestTaskAggregate:
    """Test TaskAggregate class."""

    def test_create_new_creates_initial_event(self, db):
        """Test creating a new task aggregate saves initial event."""
        task_manifest = {
            "task_id": "task-001",
            "priority": "normal",
            "device_binding": {"device_id": "device-001"},
        }

        aggregate = TaskAggregate.create_new(db, task_manifest)

        assert aggregate.task_id == "task-001"
        assert aggregate.version == 1
        assert aggregate._current_state == TaskState.PENDING

        events = aggregate.get_history()
        assert len(events) == 1
        assert events[0].event_type == "task.created"

    def test_load_from_history(self, db):
        """Test loading aggregate from event history."""
        task_manifest = {"task_id": "task-001", "priority": "normal"}

        # Create and aggregate
        created = TaskAggregate.create_new(db, task_manifest)

        # Then load it
        loaded = TaskAggregate.load(db, "task-001")

        assert loaded is not None
        assert loaded.task_id == created.task_id
        assert loaded.version == created.version

    def test_load_nonexistent_returns_none(self, db):
        """Test loading nonexistent aggregate returns None."""
        aggregate = TaskAggregate.load(db, "nonexistent-task")
        assert aggregate is None

    def test_transition_state(self, db):
        """Test state transition with event recording."""
        task_manifest = {"task_id": "task-001", "priority": "normal"}
        aggregate = TaskAggregate.create_new(db, task_manifest)
        state_machine = StateMachineFactory.create_task_state_machine("task-001")

        event = aggregate.transition_state(
            to_state=TaskState.ASSIGNED,
            event_data={"device_id": "device-001"},
            state_machine=state_machine,
        )

        assert event.event_type == "task.assigned"
        assert event.from_state == "pending"
        assert event.to_state == "assigned"
        assert aggregate.version == 2

    def test_to_dict(self, db):
        """Test converting aggregate to dictionary."""
        task_manifest = {
            "task_id": "task-001",
            "priority": "critical",
            "device_binding": {"device_id": "device-001"},
        }

        aggregate = TaskAggregate.create_new(db, task_manifest)
        state_dict = aggregate.to_dict()

        assert state_dict["task_id"] == "task-001"
        assert state_dict["state"] == "pending"
        assert state_dict["task_manifest"]["priority"] == "critical"
        assert state_dict["version"] == 1

    def test_apply_event_updates_state(self, db):
        """Test that applying events updates aggregate state."""
        task_manifest = {"task_id": "task-001", "priority": "normal"}
        aggregate = TaskAggregate.create_new(db, task_manifest)

        # Save a task.assigned event manually
        event_store = EventStore(db)
        event_store.save_event(
            entity_type="task",
            entity_id="task-001",
            event_type="task.assigned",
            event_data={"device_id": "device-001"},
            from_state="pending",
            to_state="assigned",
        )

        # Reload from history and check state
        loaded = TaskAggregate.load(db, "task-001")
        assert loaded._assigned_device_id == "device-001"

    def test_get_events_for_version(self, db):
        """Test getting events up to a specific version."""
        task_manifest = {"task_id": "task-001", "priority": "normal"}
        aggregate = TaskAggregate.create_new(db, task_manifest)
        state_machine = StateMachineFactory.create_task_state_machine("task-001")

        aggregate.transition_state(TaskState.ASSIGNED, {"device_id": "device-001"}, state_machine)
        aggregate.transition_state(TaskState.RUNNING, {}, state_machine)
        aggregate.transition_state(TaskState.SUCCESS, {"result": "OK"}, state_machine)

        events_up_to_v3 = aggregate.get_events_for_version(3)
        assert len(events_up_to_v3) == 3

        all_events = aggregate.get_history()
        assert len(all_events) == 4


class TestDeviceAggregate:
    """Test DeviceAggregate class."""

    def test_create_new_creates_initial_event(self, db):
        """Test creating a new device aggregate saves initial event."""
        config = {
            "device_id": "device-001",
            "name": "Test Device",
            "capabilities": {"test": True},
        }

        aggregate = DeviceAggregate.create_new(db, config)

        assert aggregate.device_id == "device-001"
        assert aggregate.version == 1
        assert aggregate._current_state == DeviceState.OFFLINE

        events = aggregate.get_history()
        assert len(events) == 1
        assert events[0].event_type == "device.registered"

    def test_load_from_history(self, db):
        """Test loading device aggregate from event history."""
        config = {"device_id": "device-001", "name": "Test Device"}

        # Create aggregate
        created = DeviceAggregate.create_new(db, config)

        # Load it back
        loaded = DeviceAggregate.load(db, "device-001")

        assert loaded is not None
        assert loaded.device_id == created.device_id
        assert loaded.version == created.version

    def test_record_heartbeat(self, db):
        """Test recording device heartbeat."""
        config = {"device_id": "device-001", "name": "Test Device"}
        aggregate = DeviceAggregate.create_new(db, config)

        heartbeat_data = {
            "status": "idle",
            "capabilities": {"test": True, "new_cap": False},
        }

        event = aggregate.record_heartbeat(heartbeat_data)

        assert event.event_type == "device.heartbeat"
        assert aggregate._last_heartbeat_at is not None
        assert aggregate.version == 2

    def test_transition_state(self, db):
        """Test device state transition."""
        config = {"device_id": "device-001", "name": "Test Device"}
        aggregate = DeviceAggregate.create_new(db, config)
        state_machine = StateMachineFactory.create_device_state_machine("device-001")

        event = aggregate.transition_state(
            to_state=DeviceState.RUNNING,
            event_data={"reason": "Task assigned"},
            state_machine=state_machine,
        )

        assert event.to_state == "running"
        assert aggregate._current_state == DeviceState.RUNNING

    def test_to_dict(self, db):
        """Test converting device aggregate to dictionary."""
        config = {"device_id": "device-001", "name": "Test Device"}

        aggregate = DeviceAggregate.create_new(db, config)
        state_dict = aggregate.to_dict()

        assert state_dict["device_id"] == "device-001"
        assert state_dict["state"] == DeviceState.OFFLINE.value
        assert state_dict["config"]["name"] == "Test Device"
        assert state_dict["version"] == 1

    def test_apply_heartbeat_updates_state(self, db):
        """Test that heartbeat updates device state and capabilities."""
        config = {"device_id": "device-001", "name": "Test Device"}
        aggregate = DeviceAggregate.create_new(db, config)

        heartbeat_data = {
            "status": "running",
            "capabilities": {"test": True, "new_cap": True},
        }

        aggregate.record_heartbeat(heartbeat_data)

        assert aggregate._current_state == DeviceState.RUNNING
        assert aggregate._capabilities["new_cap"] == True
        assert aggregate._last_heartbeat_at is not None


class TestEventSourcingIntegration:
    """Integration tests for EventSourcing with StateMachine."""

    def test_task_lifecycle_with_eventsourcing(self, db):
        """Test full task lifecycle with EventSourcing."""
        task_manifest = {"task_id": "task-001", "priority": "normal"}
        aggregate = TaskAggregate.create_new(db, task_manifest)
        state_machine = StateMachineFactory.create_task_state_machine("task-001", EventStore(db))

        # Complete task lifecycle
        aggregate.transition_state(TaskState.ASSIGNED, {"device_id": "device-001"}, state_machine)
        aggregate.transition_state(TaskState.RUNNING, {}, state_machine)
        aggregate.transition_state(TaskState.SUCCESS, {"result": "OK"}, state_machine)

        # Verify all events were saved
        events = aggregate.get_history()
        assert len(events) == 4
        assert [e.event_type for e in events] == [
            "task.created",
            "task.assigned",
            "task_started",
            "task.completed",
        ]

        # Reload and verify state reconstruction
        reloaded = TaskAggregate.load(db, "task-001")
        assert reloaded._current_state == TaskState.SUCCESS
        assert reloaded._result == {"result": "OK"}

    def test_device_lifecycle_with_eventsourcing(self, db):
        """Test full device lifecycle with EventSourcing."""
        config = {"device_id": "device-001", "name": "Test Device"}
        aggregate = DeviceAggregate.create_new(db, config)
        state_machine = StateMachineFactory.create_device_state_machine("device-001")

        # Device lifecycle
        aggregate.transition_state(DeviceState.RUNNING, {}, state_machine)
        aggregate.record_heartbeat({"status": "running", "capabilities": {}})
        aggregate.transition_state(DeviceState.IDLE, {}, state_machine)

        # Verify events
        events = aggregate.get_history()
        assert len(events) == 4
        assert events[0].event_type == "device.registered"
        assert events[1].to_state == "running"
        assert events[2].event_type == "device.heartbeat"
        assert events[3].to_state == "idle"

    def test_correlation_between_task_and_device_events(self, db):
        """Test that related events can be correlated."""
        task_manifest = {"task_id": "task-001", "priority": "normal"}
        correlation_id = "workflow-123"

        # Create task with correlation
        task_agg = TaskAggregate.create_new(db, task_manifest)
        task_event = task_agg.save_event(
            event_type="task.assigned",
            event_data={"device_id": "device-001"},
            correlation_id=correlation_id,
            to_state="assigned",
        )

        # Create device with same correlation
        config = {"device_id": "device-001", "name": "Test Device"}
        device_agg = DeviceAggregate.create_new(db, config)
        device_agg.save_event(
            event_type="device.heartbeat",
            event_data={"task_id": "task-001"},
            correlation_id=correlation_id,
            to_state="running",
        )

        # Query by correlation
        event_store = EventStore(db)
        correlated_events = event_store.get_events_by_correlation_id(correlation_id)

        assert len(correlated_events) == 2
        assert all(e.correlation_id == correlation_id for e in correlated_events)
