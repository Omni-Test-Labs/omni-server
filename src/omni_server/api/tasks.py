"""API endpoints for task management."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from omni_server.database import get_db
from omni_server.models import ExecutionResult, TaskManifest
from omni_server.queue import TaskQueueManager

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
