"""API endpoints for task management."""

from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from omni_server.ai import RCAnalysisService
from omni_server.config import Settings
from omni_server.database import get_db
from omni_server.events import get_event_bus, TaskEvent
from omni_server.models import ExecutionResult, TaskManifest
from omni_server.queue import TaskQueueManager

router = APIRouter(prefix="/tasks", tags=["tasks"])

_settings = Settings()
event_bus = get_event_bus()


async def publish_task_event(event_type: str, task_id: str, **kwargs):
    event = TaskEvent(event_type=event_type, task_id=task_id, **kwargs)
    await event_bus.publish(f"task:{task_id}", event.model_dump())


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
    TaskQueueManager.enqueue_task(
        db=db,
        task_id=task.task_id,
        device_binding=task.device_binding,
        task_manifest=task.model_dump(),
    )
    await publish_task_event(
        "task.created",
        task.task_id,
        priority=task.priority.value,
    )
    return {"task_id": task.task_id, "status": "pending"}


@router.put("/{task_id}/assign")
async def assign_task(
    task_id: str,
    assign_request: dict,
    db: Session = Depends(get_db),
) -> dict:
    device_id = assign_request.get("device_id")
    if not device_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_id required")

    task = TaskQueueManager.assign_task(db, task_id, device_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or not pending"
        )

    await publish_task_event(
        "task.assigned",
        task_id,
        device_id=device_id,
        status=task.status,
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
    task = TaskQueueManager.record_result(db, task_id, result.model_dump())
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    event_type = "task.completed" if task.status == "success" else "task.failed"
    await publish_task_event(
        event_type,
        task_id,
        status=task.status,
        device_id=task.assigned_device_id,
        details={"result": result.model_dump()},
    )

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


class TaskResult(BaseModel):
    task_id: str
    status: str
    error: Optional[str] = None


class BatchTaskCreateRequest(BaseModel):
    tasks: list[dict]


class BatchTaskCreateResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: list[TaskResult]


class BatchTaskAssignRequest(BaseModel):
    assignments: list[dict]


class BatchTaskCancelRequest(BaseModel):
    task_ids: list[str]


@router.post("/batch", response_model=BatchTaskCreateResponse)
async def create_tasks_batch(
    request: BatchTaskCreateRequest,
    db: Session = Depends(get_db),
) -> BatchTaskCreateResponse:
    """Create multiple tasks in a single request."""
    results = []
    successful_count = 0
    failed_count = 0

    for task_data in request.tasks:
        try:
            task = TaskManifest(**task_data)
        except Exception as e:
            results.append(
                TaskResult(
                    task_id=task_data.get("task_id", "unknown"),
                    status="failed",
                    error=f"Invalid task data: {str(e)}",
                )
            )
            failed_count += 1
            continue

        try:
            TaskQueueManager.enqueue_task(
                db=db,
                task_id=task.task_id,
                device_binding=task.device_binding,
                task_manifest=task.model_dump(),
            )
            results.append(TaskResult(task_id=task.task_id, status="created", error=None))
            successful_count += 1
        except Exception as e:
            results.append(TaskResult(task_id=task.task_id, status="failed", error=str(e)))
            failed_count += 1

    return BatchTaskCreateResponse(
        total=len(request.tasks),
        successful=successful_count,
        failed=failed_count,
        results=results,
    )


@router.post("/assign/batch")
async def assign_tasks_batch(
    request: BatchTaskAssignRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Assign multiple tasks to devices in a single request."""
    results = []
    successful_count = 0
    failed_count = 0

    for assignment in request.assignments:
        task_id = assignment.get("task_id")
        device_id = assignment.get("device_id")

        if not task_id or not device_id:
            results.append(
                {
                    "task_id": task_id or "unknown",
                    "status": "failed",
                    "error": "Missing task_id or device_id",
                }
            )
            failed_count += 1
            continue

        try:
            task = TaskQueueManager.assign_task(db, task_id, device_id)
            if task:
                results.append(
                    {
                        "task_id": task_id,
                        "status": "assigned",
                        "device_id": device_id,
                    }
                )
                successful_count += 1
            else:
                results.append({"task_id": task_id, "status": "failed", "error": "Task not found"})
                failed_count += 1
        except Exception as e:
            results.append({"task_id": task_id, "status": "failed", "error": str(e)})
            failed_count += 1

    return {
        "total": len(request.assignments),
        "successful": successful_count,
        "failed": failed_count,
        "results": results,
    }


@router.post("/cancel/batch")
async def cancel_tasks_batch(
    request: BatchTaskCancelRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Cancel multiple tasks in a single request."""
    results = []
    successful_count = 0
    failed_count = 0

    for task_id in request.task_ids:
        try:
            task = TaskQueueManager.get_task_by_id(db, task_id)
            if task and task.status in ["pending", "assigned"]:
                TaskQueueManager.update_task_status(db, task_id, "cancelled")
                results.append({"task_id": task_id, "status": "cancelled"})
                successful_count += 1
            elif task and task.status == "cancelled":
                results.append(
                    {"task_id": task_id, "status": "skipped", "error": "Already cancelled"}
                )
                failed_count += 1
            else:
                results.append(
                    {
                        "task_id": task_id,
                        "status": "failed",
                        "error": f"Task in {task.status} state cannot be cancelled",
                    }
                )
                failed_count += 1
        except Exception as e:
            results.append({"task_id": task_id, "status": "failed", "error": str(e)})
            failed_count += 1

    return {
        "total": len(request.task_ids),
        "successful": successful_count,
        "failed": failed_count,
        "results": results,
    }
