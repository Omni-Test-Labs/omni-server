"""API endpoints for task management."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from omni_server.ai import RCAnalysisService
from omni_server.config import Settings
from omni_server.database import get_db
from omni_server.models import ExecutionResult, TaskManifest
from omni_server.queue import TaskQueueManager

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

_settings = Settings()

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("", response_model=list[dict])
async def list_tasks(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List all tasks in the queue."""
    tasks = TaskQueueManager.list_tasks(db, status=status)
    return [
        {
            "task_id": t.task_id,
            "status": t.status,
            "priority": t.priority,
            "device_binding": t.device_binding,
            "assigned_device_id": t.assigned_device_id,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        }
        for t in tasks
    ]


@router.get("/{task_id}", response_model=dict)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get a specific task by ID."""
    task = TaskQueueManager.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return {
        "task_id": task.task_id,
        "task_manifest": task.task_manifest,
        "status": task.status,
        "assigned_device_id": task.assigned_device_id,
        "created_at": task.created_at.isoformat(),
        "result": task.result,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskManifest,
    db: Session = Depends(get_db),
) -> dict:
    """Create a new task in the queue."""
    TaskQueueManager.enqueue_task(
        db=db,
        task_id=task.task_id,
        device_binding=task.device_binding,
        task_manifest=task.model_dump(),
    )
    return {"task_id": task.task_id, "status": "pending"}


@router.put("/{task_id}/assign")
async def assign_task(
    task_id: str,
    assign_request: dict,
    db: Session = Depends(get_db),
) -> dict:
    """Assign a task to a specific device."""
    device_id = assign_request.get("device_id")
    if not device_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_id required")

    task = TaskQueueManager.assign_task(db, task_id, device_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or not pending"
        )

    return {
        "task_id": task.task_id,
        "status": task.status,
        "assigned_device_id": task.assigned_device_id,
    }


@router.post("/{task_id}/result")
async def record_result(
    task_id: str,
    result: ExecutionResult,
    db: Session = Depends(get_db),
) -> dict:
    """Record task execution result."""
    task = TaskQueueManager.record_result(db, task_id, result.model_dump())
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return {"task_id": task.task_id, "status": task.status}


@router.get("/{task_id}/rca", response_model=dict)
async def get_rca_analysis(
    task_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get RCA analysis results for a task."""
    if not _settings.rca_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RCA analysis is disabled",
        )

    task = TaskQueueManager.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    rca_service = RCAnalysisService(_settings)
    result = await rca_service.analyze_task(db, task_id, force_refresh=False)

    return {
        "task_id": task_id,
        "rca": result.to_dict(),
    }


@router.post("/{task_id}/rca", response_model=dict)
async def trigger_rca_analysis(
    task_id: str,
    request_data: dict = {},
    db: Session = Depends(get_db),
) -> dict:
    """Trigger RCA analysis for a task."""
    force_refresh = request_data.get("force_refresh", False)

    if not _settings.rca_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RCA analysis is disabled",
        )

    task = TaskQueueManager.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    rca_service = RCAnalysisService(_settings)
    result = await rca_service.analyze_task(db, task_id, force_refresh=force_refresh)

    return {
        "task_id": task_id,
        "rca": result.to_dict(),
    }


@router.get("/{task_id}/rca/status", response_model=dict)
async def get_rca_status(
    task_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Check if RCA analysis is available for a task."""
    if not _settings.rca_enabled:
        return {"rca_enabled": False, "rca_available": False}

    from omni_server.models import TaskRCADB

    task = TaskQueueManager.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    rca_db = db.query(TaskRCADB).filter(TaskRCADB.task_id == task_id).first()
    if rca_db and rca_db.cache_hit:
        return {
            "rca_enabled": True,
            "rca_available": True,
            "analyzed_at": rca_db.analyzed_at.isoformat() if rca_db.analyzed_at else None,
        }

    return {
        "rca_enabled": True,
        "rca_available": False,
    }
