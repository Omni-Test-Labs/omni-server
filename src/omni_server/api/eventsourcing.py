"""API endpoints for EventSourcing history and replay."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from omni_server.database import get_db
from omni_server.eventstore import EventStore, TaskAggregate, DeviceAggregate
from omni_server.models import StateEventDB

router = APIRouter(prefix="/eventsourcing", tags=["eventsourcing"])


@router.get("/{entity_type}/{entity_id}/history")
async def get_entity_history(
    entity_type: str,
    entity_id: str,
    limit: Optional[int] = None,
    from_version: Optional[int] = None,
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get event history for an entity."""
    if entity_type not in ["task", "device"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type: {entity_type}. Must be 'task' or 'device'",
        )

    event_store = EventStore(db)
    events = event_store.get_events(entity_type, entity_id, limit=limit, from_version=from_version)

    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "event_type": e.event_type,
            "from_state": e.from_state,
            "to_state": e.to_state,
            "event_data": e.event_data,
            "timestamp": e.timestamp.isoformat(),
            "version": e.version,
            "correlation_id": e.correlation_id,
        }
        for e in events
    ]


@router.get("/{entity_type}/{entity_id}/replay")
async def replay_entity(
    entity_type: str,
    entity_id: str,
    to_version: Optional[int] = None,
    db: Session = Depends(get_db),
) -> dict:
    """Replay events to get entity state at a specific version."""
    if entity_type not in ["task", "device"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type: {entity_type}. Must be 'task' or 'device'",
        )

    if entity_type == "task":
        aggregate = TaskAggregate.load(db, entity_id)
    else:
        aggregate = DeviceAggregate.load(db, entity_id)

    if aggregate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_type.capitalize()} {entity_id} not found",
        )

    if to_version:
        if to_version > aggregate.version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Version {to_version} does not exist (current version: {aggregate.version})",
            )
        events = aggregate.get_events_for_version(to_version)
        aggregate = (
            TaskAggregate(entity_id, EventStore(db))
            if entity_type == "task"
            else DeviceAggregate(entity_id, EventStore(db))
        )
        for event in events:
            aggregate._apply_event(event)

    return {
        "entity_type": aggregate.entity_type,
        "entity_id": aggregate.entity_id,
        "version": to_version if to_version else aggregate.version,
        "state": aggregate.to_dict(),
    }


@router.get("/{entity_type}/{entity_id}/events/{event_id}")
async def get_event(
    entity_type: str,
    entity_id: str,
    event_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get a specific event by ID."""
    event = (
        db.query(StateEventDB)
        .filter(
            StateEventDB.id == event_id,
            StateEventDB.entity_type == entity_type,
            StateEventDB.entity_id == entity_id,
        )
        .first()
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return {
        "id": event.id,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "event_type": event.event_type,
        "from_state": event.from_state,
        "to_state": event.to_state,
        "event_data": event.event_data,
        "timestamp": event.timestamp.isoformat(),
        "version": event.version,
        "correlation_id": event.correlation_id,
        "causation_id": event.causation_id,
    }


@router.get("/correlation/{correlation_id}")
async def get_correlated_events(
    correlation_id: str,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get all events with the same correlation ID."""
    event_store = EventStore(db)
    events = event_store.get_events_by_correlation_id(correlation_id, limit=limit)

    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "event_type": e.event_type,
            "from_state": e.from_state,
            "to_state": e.to_state,
            "timestamp": e.timestamp.isoformat(),
            "version": e.version,
        }
        for e in events
    ]


@router.get("/date-range")
async def get_events_by_date_range(
    entity_type: str,
    from_date: datetime,
    to_date: datetime,
    entity_ids: Optional[List[str]] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get events within a date range for an entity type."""
    if entity_type not in ["task", "device"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type: {entity_type}. Must be 'task' or 'device'",
        )

    event_store = EventStore(db)
    events = event_store.get_events_by_date_range(
        entity_type, from_date, to_date, entity_ids=entity_ids, limit=limit
    )

    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "event_type": e.event_type,
            "from_state": e.from_state,
            "to_state": e.to_state,
            "timestamp": e.timestamp.isoformat(),
            "version": e.version,
        }
        for e in events
    ]


__all__ = ["router"]
