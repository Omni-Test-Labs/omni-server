"""EventStore implementation for EventSourcing pattern."""

import logging
from datetime import datetime
from typing import Any, List, Optional, Callable
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from omni_server.models import StateEventDB

logger = logging.getLogger(__name__)


class EventStore:
    """Event Store for managing state transition events (EventSourcing)."""

    def __init__(self, db: Session):
        """Initialize EventStore with database session."""
        self.db = db

    def save_event(
        self,
        entity_type: str,
        entity_id: str,
        event_type: str,
        event_data: dict[str, Any],
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        causation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> StateEventDB:
        """Save a new state transition event."""
        version = self._get_next_version(entity_type, entity_id)

        event = StateEventDB(
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            event_data=event_data,
            timestamp=datetime.utcnow(),
            version=version,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return event

    def get_events(
        self,
        entity_type: str,
        entity_id: str,
        limit: Optional[int] = None,
        from_version: Optional[int] = None,
    ) -> List[StateEventDB]:
        """Get all events for an entity."""
        query = self.db.query(StateEventDB).filter(
            StateEventDB.entity_type == entity_type,
            StateEventDB.entity_id == entity_id,
        )

        if from_version:
            query = query.filter(StateEventDB.version >= from_version)

        query = query.order_by(StateEventDB.version.asc())

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_event_at_version(
        self, entity_type: str, entity_id: str, version: int
    ) -> Optional[StateEventDB]:
        """Get a specific event at a given version."""
        return (
            self.db.query(StateEventDB)
            .filter(
                StateEventDB.entity_type == entity_type,
                StateEventDB.entity_id == entity_id,
                StateEventDB.version == version,
            )
            .first()
        )

    def get_events_by_correlation_id(
        self, correlation_id: str, limit: Optional[int] = None
    ) -> List[StateEventDB]:
        """Get all events with the same correlation ID."""
        query = (
            self.db.query(StateEventDB)
            .filter(StateEventDB.correlation_id == correlation_id)
            .order_by(StateEventDB.timestamp.asc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_events_by_date_range(
        self,
        entity_type: str,
        from_date: datetime,
        to_date: datetime,
        entity_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[StateEventDB]:
        """Get events within a date range for an entity type."""
        query = self.db.query(StateEventDB).filter(
            StateEventDB.entity_type == entity_type,
            StateEventDB.timestamp >= from_date,
            StateEventDB.timestamp <= to_date,
        )

        if entity_ids:
            query = query.filter(StateEventDB.entity_id.in_(entity_ids))

        query = query.order_by(StateEventDB.timestamp.desc())

        if limit:
            query = query.limit(limit)

        return query.all()

    def replay_events(
        self,
        entity_type: str,
        entity_id: str,
        event_handler: Callable[[StateEventDB], None],
        to_version: Optional[int] = None,
    ) -> None:
        """Replay events for an entity through a handler function."""
        events = self.get_events(entity_type, entity_id)

        if to_version:
            events = [e for e in events if e.version <= to_version]

        for event in events:
            event_handler(event)

    def delete_events(
        self, entity_type: str, entity_id: str, before_version: Optional[int] = None
    ) -> int:
        """Delete events for an entity (use carefully for archiving)."""
        query = self.db.query(StateEventDB).filter(
            StateEventDB.entity_type == entity_type,
            StateEventDB.entity_id == entity_id,
        )

        if before_version:
            query = query.filter(StateEventDB.version < before_version)

        count = query.count()
        query.delete()
        self.db.commit()

        return count

    def get_entity_version(self, entity_type: str, entity_id: str) -> int:
        """Get the current version of an entity."""
        event = (
            self.db.query(StateEventDB)
            .filter(
                StateEventDB.entity_type == entity_type,
                StateEventDB.entity_id == entity_id,
            )
            .order_by(StateEventDB.version.desc())
            .first()
        )
        return event.version if event else 0

    def _get_next_version(self, entity_type: str, entity_id: str) -> int:
        """Get the next version number for an entity."""
        current_version = self.get_entity_version(entity_type, entity_id)
        return current_version + 1


__all__ = ["EventStore"]
