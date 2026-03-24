"""Heartbeat cleanup service to prevent database bloat."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from omni_server.config import Settings
from omni_server.models import DeviceHeartbeatDB

logger = logging.getLogger(__name__)


class HeartbeatCleanupService:
    """Service for cleaning up old heartbeat records."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()

    def cleanup_old_heartbeats(self, db: Session) -> Dict[str, Any]:
        """Clean up heartbeat records older than retention period.

        Args:
            db: Database session

        Returns:
            Dictionary with cleanup statistics
        """
        if not self.settings.heartbeat_cleanup_enabled:
            return {"message": "Heartbeat cleanup is disabled", "deleted_count": 0}

        retention_cutoff = datetime.utcnow() - timedelta(
            days=self.settings.heartbeat_retention_days
        )

        query = db.query(DeviceHeartbeatDB).filter(DeviceHeartbeatDB.last_seen < retention_cutoff)

        count = query.count()

        if count == 0:
            logger.info("No old heartbeats to clean up")
            return {
                "message": "No old heartbeats to clean up",
                "deleted_count": 0,
                "cutoff_time": retention_cutoff.isoformat(),
            }

        query.delete(synchronize_session=False)
        db.commit()

        logger.info(
            f"Cleaned up {count} heartbeat records older than {self.settings.heartbeat_retention_days} days"
        )

        return {
            "message": f"Successfully cleaned up {count} heartbeat records",
            "deleted_count": count,
            "cutoff_time": retention_cutoff.isoformat(),
            "retention_days": self.settings.heartbeat_retention_days,
        }

    def get_heartbeat_stats(self, db: Session) -> Dict[str, Any]:
        """Get heartbeat statistics.

        Args:
            db: Database session

        Returns:
            Dictionary with heartbeat statistics
        """
        total_count = db.query(DeviceHeartbeatDB).count()

        retention_cutoff = datetime.utcnow() - timedelta(
            days=self.settings.heartbeat_retention_days
        )
        old_count = (
            db.query(DeviceHeartbeatDB)
            .filter(DeviceHeartbeatDB.last_seen < retention_cutoff)
            .count()
        )

        recent_count = total_count - old_count

        idle_count = db.query(DeviceHeartbeatDB).filter(DeviceHeartbeatDB.status == "idle").count()
        running_count = (
            db.query(DeviceHeartbeatDB).filter(DeviceHeartbeatDB.status == "running").count()
        )
        offline_count = (
            db.query(DeviceHeartbeatDB).filter(DeviceHeartbeatDB.status == "offline").count()
        )

        return {
            "total_heartbeats": total_count,
            "old_heartbeats": old_count,
            "recent_heartbeats": recent_count,
            "idle_devices": idle_count,
            "running_devices": running_count,
            "offline_devices": offline_count,
            "retention_days": self.settings.heartbeat_retention_days,
            "cutoff_time": retention_cutoff.isoformat(),
            "cleanup_enabled": self.settings.heartbeat_cleanup_enabled,
        }
