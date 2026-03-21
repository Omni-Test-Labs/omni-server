"""Tests for task dependencies and device locks APIs."""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from omni_server.main import app
from omni_server.database import get_db
from omni_server.models import TaskQueueDB, TaskDependencyDB, DeviceLockDB
from omni_server.api.dependencies import (
    TaskDependencyRequest,
    DeviceLockRequest,
    DeviceStatusResponse,
)


@pytest.fixture
def db_session():
    """Create a test database session."""
    from omni_server.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session):
    """Create a test client with database session override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_test_task(db: Session, task_id: str, priority: str = "normal") -> TaskQueueDB:
    """Helper to create a test task."""
    task = TaskQueueDB(
        task_id=task_id,
        status="pending",
        priority=priority,
        device_binding={"device_id": "test_device", "device_type": "test"},
        task_manifest={"task_id": task_id, "schema_version": "1.0.0", "pipeline": []},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# Task Dependency Tests


def test_get_task_dependencies_empty(client: TestClient, db_session: Session):
    """Test getting dependencies for a task with no dependencies."""
    task = create_test_task(db_session, "test_task_1")

    response = client.get(f"/api/v1/tasks/{task.id}/dependencies")
    assert response.status_code == 200
    assert response.json() == []


def test_create_task_dependency_success(client: TestClient, db_session: Session):
    """Test creating a task dependency successfully."""
    task1 = create_test_task(db_session, "test_task_1")
    task2 = create_test_task(db_session, "test_task_2")

    dependency_request = TaskDependencyRequest(
        task_id_one=task1.id,
        task_id_two=task2.id,
        dependency_type="after_complete",
    )

    response = client.post(
        f"/api/v1/tasks/{task1.id}/dependencies",
        json=dependency_request.model_dump(),
    )
    assert response.status_code == 201

    data = response.json()
    assert data["task_id_one"] == task1.task_id
    assert data["task_id_two"] == task2.task_id
    assert data["dependency_type"] == "after_complete"
    assert data["status"] == "active"


def test_create_duplicate_dependency(client: TestClient, db_session: Session):
    """Test that creating a duplicate dependency raises 409."""
    task1 = create_test_task(db_session, "test_task_1")
    task2 = create_test_task(db_session, "test_task_2")

    dependency_request = TaskDependencyRequest(
        task_id_one=task1.id,
        task_id_two=task2.id,
        dependency_type="after_complete",
    )

    response1 = client.post(
        f"/api/v1/tasks/{task1.id}/dependencies",
        json=dependency_request.model_dump(),
    )
    assert response1.status_code == 201

    response2 = client.post(
        f"/api/v1/tasks/{task1.id}/dependencies",
        json=dependency_request.model_dump(),
    )
    assert response2.status_code == 409
    assert "already exists" in response2.json()["detail"]


def test_create_dependency_invalid_type(client: TestClient, db_session: Session):
    """Test that creating a dependency with invalid type raises 400."""
    task1 = create_test_task(db_session, "test_task_1")
    task2 = create_test_task(db_session, "test_task_2")

    dependency_request = TaskDependencyRequest(
        task_id_one=task1.id,
        task_id_two=task2.id,
        dependency_type="invalid_type",
    )

    response = client.post(
        f"/api/v1/tasks/{task1.id}/dependencies",
        json=dependency_request.model_dump(),
    )
    assert response.status_code == 400
    assert "dependency_type must be" in response.json()["detail"]


def test_create_dependency_nonexistent_task(client: TestClient, db_session: Session):
    """Test that creating a dependency for non-existent task raises 404."""
    task1 = create_test_task(db_session, "test_task_1")

    dependency_request = TaskDependencyRequest(
        task_id_one=task1.id,
        task_id_two=99999,  # Non-existent task ID
        dependency_type="after_complete",
    )

    response = client.post(
        f"/api/v1/tasks/{task1.id}/dependencies",
        json=dependency_request.model_dump(),
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_resolve_task_dependency(client: TestClient, db_session: Session):
    """Test resolving a task dependency."""
    task1 = create_test_task(db_session, "test_task_1")
    task2 = create_test_task(db_session, "test_task_2")

    dependency_request = TaskDependencyRequest(
        task_id_one=task1.id,
        task_id_two=task2.id,
        dependency_type="after_complete",
    )

    create_response = client.post(
        f"/api/v1/tasks/{task1.id}/dependencies",
        json=dependency_request.model_dump(),
    )
    assert create_response.status_code == 201

    dependency_id = create_response.json()["id"]

    resolve_response = client.put(f"/api/v1/tasks/{task1.id}/dependencies/{dependency_id}/resolve")
    assert resolve_response.status_code == 200

    data = resolve_response.json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None


def test_delete_task_dependency(client: TestClient, db_session: Session):
    """Test deleting a task dependency."""
    task1 = create_test_task(db_session, "test_task_1")
    task2 = create_test_task(db_session, "test_task_2")

    dependency_request = TaskDependencyRequest(
        task_id_one=task1.id,
        task_id_two=task2.id,
        dependency_type="after_complete",
    )

    create_response = client.post(
        f"/api/v1/tasks/{task1.id}/dependencies",
        json=dependency_request.model_dump(),
    )
    assert create_response.status_code == 201

    dependency_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/v1/tasks/{task1.id}/dependencies/{dependency_id}")
    assert delete_response.status_code == 204


# Device Lock Tests


def test_get_device_lock_status_unlocked(client: TestClient, db_session: Session):
    """Test getting lock status for an unlocked device."""
    response = client.get("/api/v1/devices/test_device/lock")
    assert response.status_code == 200

    data = response.json()
    assert data["device_id"] == "test_device"
    assert data["is_locked"] is False
    assert data["lock_info"] is None


def test_acquire_device_lock_success(client: TestClient, db_session: Session):
    """Test successfully acquiring a device lock."""
    task = create_test_task(db_session, "test_task_1")

    lock_request = DeviceLockRequest(
        device_id="test_device",
        task_id=task.id,
        lock_timeout_seconds=300,
    )

    response = client.post(
        "/api/v1/devices/test_device/lock",
        json=lock_request.model_dump(),
    )
    assert response.status_code == 201

    data = response.json()
    assert data["device_id"] == "test_device"
    assert data["task_id"] == str(task.id)
    assert data["status"] == "locked"
    assert data["acquired_at"] is not None


def test_acquire_device_lock_already_locked(client: TestClient, db_session: Session):
    """Test that acquiring a lock on an already locked device raises 409."""
    task1 = create_test_task(db_session, "test_task_1")
    task2 = create_test_task(db_session, "test_task_2")

    lock_request1 = DeviceLockRequest(
        device_id="test_device",
        task_id=task1.id,
        lock_timeout_seconds=300,
    )

    response1 = client.post(
        "/api/v1/devices/test_device/lock",
        json=lock_request1.model_dump(),
    )
    assert response1.status_code == 201

    lock_request2 = DeviceLockRequest(
        device_id="test_device",
        task_id=task2.id,
        lock_timeout_seconds=300,
    )

    response2 = client.post(
        "/api/v1/devices/test_device/lock",
        json=lock_request2.model_dump(),
    )
    assert response2.status_code == 409
    assert "already locked" in response2.json()["detail"]


def test_acquire_device_lock_nonexistent_task(client: TestClient, db_session: Session):
    """Test that acquiring a lock for non-existent task raises 404."""
    lock_request = DeviceLockRequest(
        device_id="test_device",
        task_id=99999,  # Non-existent task ID
        lock_timeout_seconds=300,
    )

    response = client.post(
        "/api/v1/devices/test_device/lock",
        json=lock_request.model_dump(),
    )
    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]


def test_release_device_lock_success(client: TestClient, db_session: Session):
    """Test successfully releasing a device lock."""
    task = create_test_task(db_session, "test_task_1")

    lock_request = DeviceLockRequest(
        device_id="test_device",
        task_id=task.id,
        lock_timeout_seconds=300,
    )

    create_response = client.post(
        "/api/v1/devices/test_device/lock",
        json=lock_request.model_dump(),
    )
    assert create_response.status_code == 201

    release_response = client.delete("/api/v1/devices/test_device/lock?task_id={task.id}")
    assert release_response.status_code == 200

    data = release_response.json()
    assert data["status"] == "released"
    assert data["released_at"] is not None


def test_release_device_lock_nonexistent(client: TestClient, db_session: Session):
    """Test that releasing a non-existent lock raises 404."""
    response = client.delete("/api/v1/devices/test_device/lock?task_id=99999")
    assert response.status_code == 404
    assert "No active lock found" in response.json()["detail"]


def test_list_all_device_locks(client: TestClient, db_session: Session):
    """Test listing all device locks."""
    task1 = create_test_task(db_session, "test_task_1", priority="critical")
    task2 = create_test_task(db_session, "test_task_2", priority="high")

    # Lock device1
    lock_request1 = DeviceLockRequest(
        device_id="device1",
        task_id=task1.id,
        lock_timeout_seconds=300,
    )
    client.post("/api/v1/devices/device1/lock", json=lock_request1.model_dump())

    # Lock device2
    lock_request2 = DeviceLockRequest(
        device_id="device2",
        task_id=task2.id,
        lock_timeout_seconds=600,
    )
    client.post("/api/v1/devices/device2/lock", json=lock_request2.model_dump())

    response = client.get("/api/v1/devices/locks")
    assert response.status_code == 200

    locks = response.json()
    assert len(locks) == 2

    device1_lock = next((l for l in locks if l["device_id"] == "device1"), None)
    device2_lock = next((l for l in locks if l["device_id"] == "device2"), None)

    assert device1_lock is not None
    assert device2_lock is not None
    assert device1_lock["is_locked"] is True
    assert device2_lock["is_locked"] is True
