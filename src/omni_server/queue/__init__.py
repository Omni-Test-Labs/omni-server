"""Queue manager for task dispatch and management."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from omni_server.config import Settings
from omni_server.models import TaskQueueDB, TaskStatus
from omni_server.statemachine import (
    StateMachineFactory,
    StateMachine,
    TaskState,
    InvalidStateTransitionError,
)
from omni_server.tracing.decorators import traced, async_traced
from omni_server.utils.logging import TaskLogger

logger = logging.getLogger(__name__)

_config_cache = None
_state_machine_cache: dict = {}


def _get_task_state_machine(task_id: str, db: Optional[Session] = None) -> "StateMachine":
    """Get or create a StateMachine for task state management with EventSourcing."""
    if task_id not in _state_machine_cache:
        event_store = None
        if db:
            from omni_server.eventstore import EventStore

            event_store = EventStore(db)

        sm = StateMachineFactory.create_task_state_machine(task_id, event_store)
        _state_machine_cache[task_id] = sm
    return _state_machine_cache[task_id]


def init_rca_config(config: Settings) -> None:
    """Initialize RCA configuration for auto-trigger on task failure."""
    global _config_cache
    _config_cache = config

    if config.rca_enabled and config.auto_rca_on_failure:
        logger.info("RCA auto-trigger on task failure is enabled")
    else:
        logger.debug("RCA auto-trigger on task failure is disabled")


@async_traced("queue.trigger_rca")
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
    @traced("queue.enqueue_task")
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
    @traced("queue.poll_for_tasks")
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
    @traced("queue.assign_task")
    def assign_task(db: Session, task_id: str, device_id: str) -> Optional[TaskQueueDB]:
        """Assign a pending task to a device using StateMachine."""
        task = (
            db.query(TaskQueueDB)
            .filter(TaskQueueDB.task_id == task_id, TaskQueueDB.status == "pending")
            .first()
        )

        if task:
            sm = _get_task_state_machine(task_id, db)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(sm.transition(TaskState.ASSIGNED))
                else:
                    loop.run_until_complete(sm.transition(TaskState.ASSIGNED))
            except InvalidStateTransitionError as e:
                logger.warning(f"State transition failed for task {task_id}: {e}")
                return None

            task.status = "assigned"
            task.assigned_device_id = device_id
            task.updated_at = datetime.utcnow()
            db.commit()

        return task

    @staticmethod
    @traced("queue.update_task_status")
    def update_task_status(db: Session, task_id: str, status: str) -> Optional[TaskQueueDB]:
        """Update task status using StateMachine."""
        task = db.query(TaskQueueDB).filter(TaskQueueDB.task_id == task_id).first()

        if task:
            sm = _get_task_state_machine(task_id, db)
            target_state = TaskState(status)

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(sm.transition(target_state))
                else:
                    loop.run_until_complete(sm.transition(target_state))
            except InvalidStateTransitionError as e:
                logger.warning(f"State transition failed for task {task_id}: {e}")
                return None

            task.status = status
            task.updated_at = datetime.utcnow()
            db.commit()

        return task

    @staticmethod
    def record_result(db: Session, task_id: str, result: dict) -> Optional[TaskQueueDB]:
        """Record task execution result using StateMachine."""
        task = db.query(TaskQueueDB).filter(TaskQueueDB.task_id == task_id).first()

        if task:
            sm = _get_task_state_machine(task_id, db)
            result_status = result.get("status", "failed")
            target_state = TaskState(result_status)

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(sm.transition(target_state))
                else:
                    loop.run_until_complete(sm.transition(target_state))
            except InvalidStateTransitionError as e:
                logger.warning(f"State transition failed for task {task_id}: {e}")

            task.result = result
            task.status = result_status
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
