"""API endpoints for task dependencies and device resource locks."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from omni_server.database import get_db
from omni_server.models import (
    TaskDependencyDB,
    DeviceLockDB,
    TaskQueueDB,
    Base,
)

router = APIRouter(prefix="", tags=["dependencies", "locks"])


# Request/Response Models


class TaskDependencyRequest(BaseModel):
    """Request model for creating a task dependency."""

    task_id_one: int = Field(..., description="ID of the first task")
    task_id_two: int = Field(..., description="ID of the second task")
    dependency_type: str = Field(
        ..., description="Type of dependency: 'after_complete' or 'after_start'"
    )


class TaskDependencyResponse(BaseModel):
    """Response model for task dependency."""

    id: int
    task_id_one: str
    task_id_two: str
    dependency_type: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None


class DeviceLockRequest(BaseModel):
    """Request model for creating or updating a device lock."""

    device_id: str = Field(..., description="Device ID to lock")
    task_id: int = Field(..., description="Task ID requesting the lock")
    lock_timeout_seconds: int = Field(default=300, description="Lock timeout in seconds")


class DeviceLockResponse(BaseModel):
    """Response model for device lock."""

    id: int
    device_id: str
    task_id: str
    status: str
    lock_timeout_seconds: int
    acquired_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    created_at: datetime


class DeviceStatusResponse(BaseModel):
    """Response model for device lock status."""

    device_id: str
    is_locked: bool
    lock_info: Optional[DeviceLockResponse] = None


# Task Dependency Endpoints


@router.get(
    "/tasks/{task_id}/dependencies",
    response_model=List[TaskDependencyResponse],
    tags=["dependencies"],
)
async def get_task_dependencies(
    task_id: int,
    db: Session = Depends(get_db),
    dependency_type: Optional[str] = Query(None, description="Filter by dependency type"),
) -> List[TaskDependencyResponse]:
    """Get all dependencies for a specific task."""
    from sqlalchemy.orm import joinedload

    query = db.query(TaskDependencyDB)

    # Filter by task_id_one OR task_id_two to get all related dependencies
    tasks_in_queue = db.query(TaskQueueDB).filter(TaskQueueDB.id == task_id).first()
    if tasks_in_queue:
        query = query.filter(
            (TaskDependencyDB.task_id_one == task_id) | (TaskDependencyDB.task_id_two == task_id)
        )
    else:
        return []

    if dependency_type:
        query = query.filter(TaskDependencyDB.dependency_type == dependency_type)

    dependencies = query.all()

    # Get task IDs to map to task_id strings
    task_ids = set(dep.task_id_one for dep in dependencies) | set(
        dep.task_id_two for dep in dependencies
    )
    task_map = {
        t.id: t.task_id for t in db.query(TaskQueueDB).filter(TaskQueueDB.id.in_(task_ids)).all()
    }

    return [
        TaskDependencyResponse(
            id=dep.id,
            task_id_one=task_map.get(dep.task_id_one, ""),
            task_id_two=task_map.get(dep.task_id_two, ""),
            dependency_type=dep.dependency_type,
            status=dep.status,
            created_at=dep.created_at,
            resolved_at=dep.resolved_at,
        )
        for dep in dependencies
    ]


@router.post(
    "/tasks/{task_id}/dependencies",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskDependencyResponse,
    tags=["dependencies"],
)
async def create_task_dependency(
    task_id: int,
    dependency: TaskDependencyRequest,
    db: Session = Depends(get_db),
) -> TaskDependencyResponse:
    """Create a new task dependency."""
    # Verify both tasks exist
    task_one = db.query(TaskQueueDB).filter(TaskQueueDB.id == dependency.task_id_one).first()
    task_two = db.query(TaskQueueDB).filter(TaskQueueDB.id == dependency.task_id_two).first()

    if not task_one or not task_two:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both tasks not found",
        )

    # Validate dependency_type
    if dependency.dependency_type not in ["after_complete", "after_start"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="dependency_type must be 'after_complete' or 'after_start'",
        )

    # Check for duplicate dependency
    existing = (
        db.query(TaskDependencyDB)
        .filter(
            TaskDependencyDB.task_id_one == dependency.task_id_one,
            TaskDependencyDB.task_id_two == dependency.task_id_two,
            TaskDependencyDB.dependency_type == dependency.dependency_type,
            TaskDependencyDB.status == "active",
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dependency already exists",
        )

    # Create dependency
    db_dependency = TaskDependencyDB(
        task_id_one=dependency.task_id_one,
        task_id_two=dependency.task_id_two,
        dependency_type=dependency.dependency_type,
    )
    db.add(db_dependency)
    db.commit()
    db.refresh(db_dependency)

    return TaskDependencyResponse(
        id=db_dependency.id,
        task_id_one=task_one.task_id,
        task_id_two=task_two.task_id,
        dependency_type=db_dependency.dependency_type,
        status=db_dependency.status,
        created_at=db_dependency.created_at,
        resolved_at=db_dependency.resolved_at,
    )


@router.delete(
    "/tasks/{task_id}/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["dependencies"],
)
async def delete_task_dependency(
    task_id: int,
    dependency_id: int,
    db: Session = Depends(get_db),
):
    """Delete a task dependency."""
    dependency = db.query(TaskDependencyDB).filter(TaskDependencyDB.id == dependency_id).first()

    if not dependency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found",
        )

    db.delete(dependency)
    db.commit()


@router.put(
    "/tasks/{task_id}/dependencies/{dependency_id}/resolve",
    response_model=TaskDependencyResponse,
    tags=["dependencies"],
)
async def resolve_task_dependency(
    task_id: int,
    dependency_id: int,
    db: Session = Depends(get_db),
) -> TaskDependencyResponse:
    """Mark a task dependency as resolved."""
    dependency = db.query(TaskDependencyDB).filter(TaskDependencyDB.id == dependency_id).first()

    if not dependency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found",
        )

    dependency.status = "resolved"
    dependency.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(dependency)

    task_one = db.query(TaskQueueDB).filter(TaskQueueDB.id == dependency.task_id_one).first()
    task_two = db.query(TaskQueueDB).filter(TaskQueueDB.id == dependency.task_id_two).first()

    return TaskDependencyResponse(
        id=dependency.id,
        task_id_one=task_one.task_id if task_one else "",
        task_id_two=task_two.task_id if task_two else "",
        dependency_type=dependency.dependency_type,
        status=dependency.status,
        created_at=dependency.created_at,
        resolved_at=dependency.resolved_at,
    )


# Device Lock Endpoints


@router.get(
    "/devices/{device_id}/lock",
    response_model=DeviceStatusResponse,
    tags=["locks"],
)
async def get_device_lock_status(
    device_id: str,
    db: Session = Depends(get_db),
) -> DeviceStatusResponse:
    """Get lock status for a specific device."""
    lock = (
        db.query(DeviceLockDB)
        .filter(
            DeviceLockDB.device_id == device_id,
            DeviceLockDB.status == "locked",
        )
        .first()
    )

    if not lock:
        return DeviceStatusResponse(
            device_id=device_id,
            is_locked=False,
            lock_info=None,
        )

    return DeviceStatusResponse(
        device_id=device_id,
        is_locked=True,
        lock_info=DeviceLockResponse(
            id=lock.id,
            device_id=lock.device_id,
            task_id=str(lock.task_id),
            status=lock.status,
            lock_timeout_seconds=lock.lock_timeout_seconds,
            acquired_at=lock.acquired_at,
            released_at=lock.released_at,
            created_at=lock.created_at,
        ),
    )


@router.post(
    "/devices/{device_id}/lock",
    status_code=status.HTTP_201_CREATED,
    response_model=DeviceLockResponse,
    tags=["locks"],
)
async def acquire_device_lock(
    device_id: str,
    lock_request: DeviceLockRequest,
    db: Session = Depends(get_db),
) -> DeviceLockResponse:
    """Acquire a lock on a device."""
    # Verify task exists
    task = db.query(TaskQueueDB).filter(TaskQueueDB.id == lock_request.task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Check if device is already locked
    existing_lock = (
        db.query(DeviceLockDB)
        .filter(
            DeviceLockDB.device_id == device_id,
            DeviceLockDB.status == "locked",
        )
        .first()
    )

    if existing_lock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device {device_id} is already locked by task {existing_lock.task_id}",
        )

    # Create new lock
    db_lock = DeviceLockDB(
        device_id=device_id,
        task_id=lock_request.task_id,
        status="locked",
        lock_timeout_seconds=lock_request.lock_timeout_seconds,
        acquired_at=datetime.utcnow(),
    )
    db.add(db_lock)
    db.commit()
    db.refresh(db_lock)

    return DeviceLockResponse(
        id=db_lock.id,
        device_id=db_lock.device_id,
        task_id=str(db_lock.task_id),
        status=db_lock.status,
        lock_timeout_seconds=db_lock.lock_timeout_seconds,
        acquired_at=db_lock.acquired_at,
        released_at=db_lock.released_at,
        created_at=db_lock.created_at,
    )


@router.delete(
    "/devices/{device_id}/lock",
    response_model=DeviceLockResponse,
    tags=["locks"],
)
async def release_device_lock(
    device_id: str,
    task_id: int = Query(..., description="Task ID that owns the lock"),
    db: Session = Depends(get_db),
) -> DeviceLockResponse:
    """Release a lock on a device."""
    lock = (
        db.query(DeviceLockDB)
        .filter(
            DeviceLockDB.device_id == device_id,
            DeviceLockDB.task_id == task_id,
            DeviceLockDB.status == "locked",
        )
        .first()
    )

    if not lock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active lock found for this device and task",
        )

    lock.status = "released"
    lock.released_at = datetime.utcnow()
    db.commit()
    db.refresh(lock)

    return DeviceLockResponse(
        id=lock.id,
        device_id=lock.device_id,
        task_id=str(lock.task_id),
        status=lock.status,
        lock_timeout_seconds=lock.lock_timeout_seconds,
        acquired_at=lock.acquired_at,
        released_at=lock.released_at,
        created_at=lock.created_at,
    )


@router.get(
    "/devices/locks",
    response_model=List[DeviceStatusResponse],
    tags=["locks"],
)
async def list_all_device_locks(
    status_filter: Optional[str] = Query(None, description="Filter by lock status"),
    db: Session = Depends(get_db),
) -> List[DeviceStatusResponse]:
    """List all device locks."""
    query = db.query(DeviceLockDB)

    if status_filter:
        query = query.filter(DeviceLockDB.status == status_filter)

    locks = query.all()

    # Group by device_id and get latest lock for each
    device_status_map: dict[str, DeviceLockDB] = {}
    for lock in locks:
        if lock.device_id not in device_status_map:
            device_status_map[lock.device_id] = lock
        elif lock.created_at > device_status_map[lock.device_id].created_at:
            device_status_map[lock.device_id] = lock

    return [
        DeviceStatusResponse(
            device_id=device_id,
            is_locked=lock.status == "locked",
            lock_info=DeviceLockResponse(
                id=lock.id,
                device_id=lock.device_id,
                task_id=str(lock.task_id),
                status=lock.status,
                lock_timeout_seconds=lock.lock_timeout_seconds,
                acquired_at=lock.acquired_at,
                released_at=lock.released_at,
                created_at=lock.created_at,
            )
            if lock.status == "locked"
            else None,
        )
        for device_id, lock in device_status_map.items()
    ]
