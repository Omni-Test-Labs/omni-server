"""Tests for task API endpoints."""

import pytest
from fastapi import status

from omni_server.models import TaskQueueDB, TaskStatus


class TestListTasks:
    """Test GET /api/v1/tasks endpoint."""

    def test_list_all_tasks(self, client, sample_task_manifest):
        """Test listing all tasks."""
        # Create tasks using API
        for i in range(3):
            task_manifest = sample_task_manifest.copy()
            task_manifest["task_id"] = f"task-{i:03d}"
            task_manifest["device_binding"] = {"device_id": f"device-{i}"}
            client.post("/api/v1/tasks", json=task_manifest)

        response = client.get("/api/v1/tasks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 3

    def test_list_tasks_by_status(self, client, sample_task_manifest):
        """Test listing tasks filtered by status."""
        # Create three tasks
        task1 = sample_task_manifest.copy()
        task1["task_id"] = "task-001"
        task2 = sample_task_manifest.copy()
        task2["task_id"] = "task-002"
        task3 = sample_task_manifest.copy()
        task3["task_id"] = "task-003"

        client.post("/api/v1/tasks", json=task1)
        client.post("/api/v1/tasks", json=task2)
        client.post("/api/v1/tasks", json=task3)

        # Assign two tasks to change their status
        client.put("/api/v1/tasks/task-001/assign", json={"device_id": "device-001"})

        response = client.get("/api/v1/tasks?status=pending")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        task_ids = [t["task_id"] for t in data]
        assert "task-002" in task_ids
        assert "task-003" in task_ids
        for task in data:
            assert task["status"] == "pending"


class TestGetTask:
    """Test GET /api/v1/tasks/{task_id} endpoint."""

    def test_get_existing_task(self, client, sample_task_manifest):
        """Test getting an existing task."""
        response = client.post("/api/v1/tasks", json=sample_task_manifest)
        assert response.status_code == status.HTTP_201_CREATED

        response = client.get(f"/api/v1/tasks/{sample_task_manifest['task_id']}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["task_id"] == "test-task-001"
        assert "task_manifest" in data
        assert data["status"] == "pending"

    def test_get_nonexistent_task(self, client):
        """Test getting a task that doesn't exist."""
        response = client.get("/api/v1/tasks/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


class TestCreateTask:
    """Test POST /api/v1/tasks endpoint."""

    def test_create_task_success(self, client, sample_task_manifest):
        """Test successful task creation."""
        response = client.post("/api/v1/tasks", json=sample_task_manifest)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["task_id"] == "test-task-001"
        assert data["status"] == "pending"

    def test_create_task_with_pipeline(self, client):
        """Test creating a task with pipeline steps."""
        task_manifest = {
            "schema_version": "1.0.0",
            "task_id": "task-with-pipeline",
            "created_at": "2024-03-18T10:00:00Z",
            "device_binding": {"device_id": "device-001"},
            "priority": "high",
            "timeout_seconds": 300,
            "pipeline": [
                {
                    "step_id": "step-1",
                    "order": 1,
                    "type": "shell",
                    "cmd": "echo step1",
                    "timeout_seconds": 10,
                },
                {
                    "step_id": "step-2",
                    "order": 2,
                    "type": "python",
                    "cmd": "script.py",
                    "timeout_seconds": 60,
                },
            ],
        }

        response = client.post("/api/v1/tasks", json=task_manifest)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["task_id"] == "task-with-pipeline"


class TestAssignTask:
    """Test PUT /api/v1/tasks/{task_id}/assign endpoint."""

    def test_assign_task_success(self, client, sample_task_manifest):
        """Test successful task assignment."""
        # Create task first
        client.post("/api/v1/tasks", json=sample_task_manifest)

        # Then assign it
        response = client.put(
            f"/api/v1/tasks/{sample_task_manifest['task_id']}/assign",
            json={"device_id": "device-001"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["task_id"] == sample_task_manifest["task_id"]
        assert data["status"] == "assigned"
        assert data["assigned_device_id"] == "device-001"

    def test_assign_task_missing_device_id(self, client, sample_task_manifest):
        """Test assigning a task without providing device_id."""
        # Create task first
        client.post("/api/v1/tasks", json=sample_task_manifest)

        response = client.put(f"/api/v1/tasks/{sample_task_manifest['task_id']}/assign", json={})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "device_id required" in response.json()["detail"]

    def test_assign_nonexistent_task(self, client):
        """Test assigning a task that doesn't exist."""
        response = client.put("/api/v1/tasks/nonexistent/assign", json={"device_id": "device-001"})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_assign_already_assigned_task(self, client, sample_task_manifest):
        """Test assigning a task that's already assigned."""
        # Create and assign task
        client.post("/api/v1/tasks", json=sample_task_manifest)
        client.put(
            f"/api/v1/tasks/{sample_task_manifest['task_id']}/assign",
            json={"device_id": "device-001"},
        )

        # Try to assign again - should fail since it's no longer pending
        response = client.put(
            f"/api/v1/tasks/{sample_task_manifest['task_id']}/assign",
            json={"device_id": "device-002"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestRecordResult:
    """Test POST /api/v1/tasks/{task_id}/result endpoint."""

    def test_record_result_success(self, client, sample_task_manifest):
        """Test successful result recording."""
        # Create task first
        client.post("/api/v1/tasks", json=sample_task_manifest)

        execution_result = {
            "schema_version": "1.0.0",
            "task_id": sample_task_manifest["task_id"],
            "type": "success",
            "started_at": "2024-03-18T10:00:00Z",
            "duration_seconds": 60.0,
            "device_info": {"device_id": "device-001"},
            "steps": [
                {
                    "step_id": "step-1",
                    "type": "success",
                    "started_at": "2024-03-18T10:00:00Z",
                    "completed_at": "2024-03-18T10:01:00Z",
                    "duration_seconds": 60.0,
                    "exit_code": 0,
                }
            ],
            "summary": {
                "total_steps": 1,
                "successful_steps": 1,
                "failed_steps": 0,
                "skipped_steps": 0,
                "crashed_steps": 0,
                "total_duration_seconds": 60.0,
                "total_artifacts": 0,
                "total_log_lines": 100,
            },
        }

        response = client.post(
            f"/api/v1/tasks/{sample_task_manifest['task_id']}/result", json=execution_result
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["task_id"] == sample_task_manifest["task_id"]
        assert data["status"] == "success"

    def test_record_result_nonexistent_task(self, client):
        """Test recording result for a task that doesn't exist."""
        execution_result = {
            "schema_version": "1.0.0",
            "task_id": "nonexistent",
            "type": "success",
            "started_at": "2024-03-18T10:00:00Z",
            "duration_seconds": 60.0,
            "device_info": {},
            "steps": [],
            "summary": {
                "total_steps": 0,
                "successful_steps": 0,
                "failed_steps": 0,
                "skipped_steps": 0,
                "crashed_steps": 0,
                "total_duration_seconds": 0.0,
                "total_artifacts": 0,
                "total_log_lines": 0,
            },
        }

        response = client.post("/api/v1/tasks/nonexistent/result", json=execution_result)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()
