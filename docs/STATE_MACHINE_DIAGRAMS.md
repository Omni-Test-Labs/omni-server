# State Machine State Diagrams

This document describes the state machines used in Omni-Test-Labs infrastructure.

## Task State Machine

### States

| State | Description |
|-------|-------------|
| `PENDING` | Task is queued and waiting for assignment |
| `ASSIGNED` | Task has been assigned to a device |
| `RUNNING` | Task is currently executing on a device |
| `SUCCESS` | Task completed successfully |
| `FAILED` | Task execution failed |
| `TIMEOUT` | Task exceeded execution time limit |
| `CRASHED` | Task crashed with unexpected error |
| `SKIPPED` | Task was cancelled or not executed |

### State Transitions

```
       ┌─────────┐
       │ PENDING │
       └────┬────┘
            │
            ▼
       ┌─────────┐     ┌─────────┐
       │ASSIGNED │────►│ RUNNING │
       └────┬────┘     └────┬────┘
            │               │
            │               ├──────────────┐
            │               │              │
            │               ▼              ▼
            │          ┌─────────┐   ┌─────────┐
            │          │ SUCCESS │   │  FAILED │
            │          └─────────┘   └─────────┘
            │               │              │
            │               │      ┌───────┴───────┐
            │               │      ▼               ▼
            │               │   ┌─────────┐   ┌─────────┐
            │               │   │ TIMEOUT │   │ CRASHED │
            │               │   └─────────┘   └─────────┘
            │               │
            └───────────────┴
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
          ┌─────────┐             ┌─────────┐
          │ SKIPPED │             │         │
          └─────────┘             └─────────┘
```

### Transition Rules

| From → To| Valid? | Conditions |
|----------|-------|------------|
| PENDING → ASSIGNED | ✅ | Device available |
| ASSIGNED → RUNNING | ✅ | Task starts execution |
| RUNNING → SUCCESS | ✅ | Task completes successfully |
| RUNNING → FAILED | ✅ | Task fails with error |
| RUNNING → TIMEOUT | ✅ | Task exceeds time limit |
| RUNNING → CRASHED | ✅ | Unexpected crash |
| ASSIGNED/RUNNING → SKIPPED | ✅ | Task cancelled |
| SUCCESS/FAILED/CRASHED/TIMEOUT → (any) | ❌ | Terminal states |

## Device State Machine

### States

| State | Description |
|-------|-------------|
| `IDLE` | Device is available and waiting for tasks |
| `RUNNING` | Device is currently executing a task |
| `OFFLINE` | Device is disconnected or unavailable |
| `MAINTENANCE` | Device is under maintenance |

### State Transitions

```
       ┌─────────┐
       │  IDLE   │◄────────┐
       └────┬────┘         │
            │              │
    ┌───────┴───────┐      │
    ▼               ▼      ▼
┌─────────┐   ┌─────────┐
│ RUNNING │   │ OFFLINE │
└────┬────┘   └─────────┘
     │
     ▼
┌─────────┐
│  IDLE   │
└─────────┘

┌─────────┐
│MAINTENANCE│───► IDLE
└─────────┘
```

### Transition Rules

| From → To | Valid? | Notes |
|-----------|-------|-------|
| IDLE → RUNNING | ✅ | Task assigned |
| IDLE → OFFLINE | ✅ | Disconnect |
| IDLE → MAINTENANCE | ✅ | Maintenance mode |
| RUNNING → IDLE | ✅ | Task completed |
| RUNNING → OFFLINE | ✅ | lost connection |
| OFFLINE → IDLE | ✅ | Reconnection |
| MAINTENANCE → IDLE | ✅ | Maintenance complete |

## EventSourcing Integration

All state transitions are automatically logged to the EventStore with the following metadata:

- **Entity Type**: `task` or `device`
- **Entity ID**: Unique identifier
- **Event Type**: `state.changed` or specific domain events
- **From State**: Previous state value
- **To State**: New state value
- **Timestamp**: When transition occurred
- **Correlation ID**: For tracking related events
- **Version**: Sequential version number for optimistic locking

### State Machine with EventSourcing

```
State Transition Request
         │
         ▼
┌─────────────────┐
│ Validate        │──► Invalid → Error
│ CanTransition?  │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Execute Action  │
│ (if any)        │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Update State    │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Save to Store   │──► EventStore
│ (EventSourcing) │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Notify Listeners│
└─────────────────┘
```

## Usage Examples

### Creating a Task State Machine

```python
from omni_server.statemachine import StateMachineFactory, TaskState

# Create state machine for a task
sm = StateMachineFactory.create_task_state_machine("task-123")

# Check if transition is valid
if sm.can_transition(TaskState.ASSIGNED):
    # Execute transition
    await sm.transition(TaskState.ASSIGNED)

# Get current state
current_state = sm.get_current_state()  # TaskState.ASSIGNED

# Get possible transitions
possible = sm.get_possible_transitions()  # [TaskState.RUNNING]
```

### With EventSourcing

```python
from omni_server.statemachine import StateMachineFactory
from omni_server.eventstore import EventStore

# Create state machine with event store
event_store = EventStore(db)
sm = StateMachineFactory.create_task_state_machine("task-123", event_store)

# Transition - automatically saves to EventStore
await sm.transition(TaskState.ASSIGNED)

# Events are persisted with full audit trail
events = event_store.get_events("task", "task-123")
```

## Monitoring and Observability

All state transitions are logged with structured logging:

```json
{
  "entity_type": "task",
  "entity_id": "task-123",
  "from_state": "assigned",
  "to_state": "running",
  "timestamp": "2026-03-24T22:48:00.000Z"
}
```

And traced with OpenTelemetry spans:

- `statemachine.transition` - Async operation
- Includes `task_id` or `device_id` as attributes
