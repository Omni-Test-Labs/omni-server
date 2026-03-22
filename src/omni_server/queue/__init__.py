"""Queue manager for task dispatch and management."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from omni_server.config import Settings
from omni_server.models import TaskQueueDB, TaskStatus

logger = logging.getLogger(__name__)

_config_cache = None


def init_rca_config(config: Settings) -> None:
    """Initialize RCA configuration for auto-trigger on task failure."""
    global _config_cache
    _config_cache = config

    if config.rca_enabled and config.auto_rca_on_failure:
        logger.info("RCA auto-trigger on task failure is enabled")
    else:
        logger.debug("RCA auto-trigger on task failure is disabled")


async def trigger_rca_analysis(task_id: str, db: Session) -> None:
    """Trigger RCA analysis for a failed task."""
    from omni_server.ai import RCAnalysisService

    config = _config_cache or Settings()
    if not config.rca_enabled or not config.auto_rca_on_failure:
        return

    try:
        rca_service = RCAnalysisService(config)
        await rca_service.analyze_task(db, task_id, force_refresh=True)
        logger.info(f"RCA analysis completed for task {task_id}")
    except Exception as e:
        logger.error(f"Failed to trigger RCA analysis for task {task_id}: {e}")


class TaskQueueManager:
    """Manages task queue operations."""

    @staticmethod
    def enqueue_task(
        db: Session, task_id: str, device_binding: dict, task_manifest: dict
    ) -> TaskQueueDB:
        """Add a task to the queue."""
        task = TaskQueueDB(
            task_id=task_id,
            device_binding=device_binding,
            task_manifest=task_manifest,
            priority=task_manifest.get("priority", "normal"),
        )
        db.add(task)
        db.commit()
        return task

    @staticmethod
    def poll_for_tasks(db: Session, device_id: str, limit: int = 1) -> list[TaskQueueDB]:
        """Poll for pending tasks assigned to a device."""
        now = datetime.utcnow()
        timeout = timedelta(seconds=300)

        return (
            db.query(TaskQueueDB)
            .filter(
                and_(
                    TaskQueueDB.status == "assigned",
                    TaskQueueDB.assigned_device_id == device_id,
                    TaskQueueDB.updated_at >= now - timeout,
                )
            )
            .order_by(TaskQueueDB.priority.desc(), TaskQueueDB.created_at)
            .limit(limit)
            .all()
        )

    @staticmethod
    def assign_task(db: Session, task_id: str, device_id: str) -> Optional[TaskQueueDB]:
        """Assign a pending task to a device."""
        task = (
            db.query(TaskQueueDB)
            .filter(TaskQueueDB.task_id == task_id, TaskQueueDB.status == "pending")
            .first()
        )

        if task:
            task.status = "assigned"
            task.assigned_device_id = device_id
            task.updated_at = datetime.utcnow()
            db.commit()

        return task

    @staticmethod
    def update_task_status(db: Session, task_id: str, status: str) -> Optional[TaskQueueDB]:
        """Update task status."""
        task = db.query(TaskQueueDB).filter(TaskQueueDB.task_id == task_id).first()

        if task:
            task.status = status
            task.updated_at = datetime.utcnow()
            db.commit()

        return task

    @staticmethod
    def record_result(db: Session, task_id: str, result: dict) -> Optional[TaskQueueDB]:
        """Record task execution result."""
        task = db.query(TaskQueueDB).filter(TaskQueueDB.task_id == task_id).first()

        if task:
            task.result = result
            task.status = result.get("status", "failed")
            task.updated_at = datetime.utcnow()
            db.commit()

            if task.status == "failed":
                config = _config_cache or Settings()
                if config.rca_enabled and config.auto_rca_on_failure:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(trigger_rca_analysis(task_id, db))
                        else:
                            loop.run_until_complete(trigger_rca_analysis(task_id, db))
                    except RuntimeError:
                        logger.warning(f"No event loop available for task {task_id}, skipping RCA")

        return task

    @staticmethod
    def get_task_by_id(db: Session, task_id: str) -> Optional[TaskQueueDB]:
        """Get a task by ID."""
        return db.query(TaskQueueDB).filter(TaskQueueDB.task_id == task_id).first()

    @staticmethod
    def list_tasks(
        db: Session, status: Optional[str] = None, limit: int = 100
    ) -> list[TaskQueueDB]:
        """List tasks with optional status filter."""
        query = db.query(TaskQueueDB)
        if status:
            query = query.filter(TaskQueueDB.status == status)
        return query.order_by(TaskQueueDB.created_at.desc()).limit(limit).all()
