"""Tests for TaskQueueManager."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import and_, or_

from omni_server.models import TaskQueueDB, TaskStatus
from omni_server.queue import TaskQueueManager


class TestEnqueueTask:
    """Test enqueue_task method."""

    def test_enqueue_task_creates_record(self, db):
        """Test that enqueue_task creates a database record."""
        task_id = "task-001"
        device_binding = {"device_id": "device-001"}
        task_manifest = {
            "schema_version": "1.0.0",
            "priority": "normal",
        }

        task = TaskQueueManager.enqueue_task(db, task_id, device_binding, task_manifest)

        assert task.task_id == task_id
        assert task.status == "pending"
        assert task.device_binding == device_binding
        assert task.task_manifest == task_manifest
        assert task.priority == "normal"
        assert task.assigned_device_id is None

    def test_enqueue_task_with_priority(self, db):
        """Test that enqueue_task extracts priority from manifest."""
        task_manifest = {
            "schema_version": "1.0.0",
            "priority": "critical",
        }

        task = TaskQueueManager.enqueue_task(db, "task-001", {"device_id": "d1"}, task_manifest)

        assert task.priority == "critical"


class TestPollForTasks:
    """Test poll_for_tasks method."""

    def test_poll_for_assigned_tasks(self, db):
        """Test polling for assigned tasks."""
        # Create an assigned task
        TaskQueueManager.enqueue_task(
            db,
            "task-001",
            {"device_id": "device-001"},
            {"priority": "normal"},
        )
        TaskQueueManager.assign_task(db, "task-001", "device-001")

        # Poll for tasks
        tasks = TaskQueueManager.poll_for_tasks(db, "device-001")

        assert len(tasks) == 1
        assert tasks[0].task_id == "task-001"
        assert tasks[0].assigned_device_id == "device-001"

    def test_poll_for_limit(self, db):
        """Test that poll_for_tasks respects the limit."""
        # Create multiple assigned tasks
        for i in range(5):
            TaskQueueManager.enqueue_task(
                db,
                f"task-{i:03d}",
                {"device_id": "device-001"},
                {"priority": "normal"},
            )
            TaskQueueManager.assign_task(db, f"task-{i:03d}", "device-001")

        # Poll with limit
        tasks = TaskQueueManager.poll_for_tasks(db, "device-001", limit=3)

        assert len(tasks) == 3


class TestAssignTask:
    """Test assign_task method."""

    def test_assign_task_success(self, db):
        """Test successful task assignment."""
        TaskQueueManager.enqueue_task(
            db, "task-001", {"device_id": "device-001"}, {"priority": "normal"}
        )

        task = TaskQueueManager.assign_task(db, "task-001", "device-001")

        assert task is not None
        assert task.status == "assigned"
        assert task.assigned_device_id == "device-001"

    def test_assign_unknown_task(self, db):
        """Test assigning a task that doesn't exist."""
        task = TaskQueueManager.assign_task(db, "nonexistent", "device-001")
        assert task is None

    def test_assign_already_assigned_task(self, db):
        """Test assigning a task that's already assigned."""
        TaskQueueManager.enqueue_task(db, "task-001", {}, {})

        # First assignment
        TaskQueueManager.assign_task(db, "task-001", "device-001")

        # Second assignment should fail
        task = TaskQueueManager.assign_task(db, "task-001", "device-002")
        # Task is no longer pending, so assignment should fail
        assert task is None or task.assigned_device_id == "device-001"


class TestUpdateTaskStatus:
    """Test update_task_status method."""

    def test_update_task_status_success(self, db):
        """Test successful status update."""
        TaskQueueManager.enqueue_task(db, "task-001", {}, {})

        task = TaskQueueManager.update_task_status(db, "task-001", "assigned")

        assert task is not None
        assert task.status == "assigned"

    def test_update_task_status_to_completed(self, db):
        """Test updating status to a completed state."""
        TaskQueueManager.enqueue_task(db, "task-001", {}, {})

        task = TaskQueueManager.update_task_status(db, "task-001", "success")

        assert task is not None
        assert task.status == "success"

    def test_update_unknown_task(self, db):
        """Test updating status of a task that doesn't exist."""
        task = TaskQueueManager.update_task_status(db, "nonexistent", "success")
        assert task is None


class TestRecordResult:
    """Test record_result method."""

    def test_record_result_success(self, db):
        """Test recording task result."""
        TaskQueueManager.enqueue_task(db, "task-001", {}, {})

        result = {
            "schema_version": "1.0.0",
            "task_id": "task-001",
            "status": "success",
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

        task = TaskQueueManager.record_result(db, "task-001", result)

        assert task is not None
        assert task.result == result
        assert task.status == "success"

    def test_record_unknown_task(self, db):
        """Test recording result for a task that doesn't exist."""
        task = TaskQueueManager.record_result(db, "nonexistent", {})
        assert task is None


class TestGetTaskById:
    """Test get_task_by_id method."""

    def test_get_existing_task(self, db):
        """Test getting an existing task."""
        TaskQueueManager.enqueue_task(db, "task-001", {}, {})

        task = TaskQueueManager.get_task_by_id(db, "task-001")

        assert task is not None
        assert task.task_id == "task-001"

    def test_get_nonexistent_task(self, db):
        """Test getting a task that doesn't exist."""
        task = TaskQueueManager.get_task_by_id(db, "nonexistent")
        assert task is None


class TestListTasks:
    """Test list_tasks method."""

    def test_list_all_tasks(self, db):
        """Test listing all tasks."""
        for i in range(3):
            TaskQueueManager.enqueue_task(db, f"task-{i:03d}", {"device_id": f"device-{i}"}, {})

        tasks = TaskQueueManager.list_tasks(db)

        assert len(tasks) == 3

    def test_list_tasks_by_status(self, db):
        """Test listing tasks filtered by status."""
        TaskQueueManager.enqueue_task(db, "task-001", {}, {})
        TaskQueueManager.enqueue_task(db, "task-002", {}, {})
        TaskQueueManager.update_task_status(db, "task-001", "assigned")

        pending_tasks = TaskQueueManager.list_tasks(db, status="pending")
        assigned_tasks = TaskQueueManager.list_tasks(db, status="assigned")

        assert len(pending_tasks) == 1
        assert len(assigned_tasks) == 1
        assert pending_tasks[0].task_id == "task-002"
        assert assigned_tasks[0].task_id == "task-001"

    def test_list_tasks_with_limit(self, db):
        """Test that list_tasks respects the limit."""
        for i in range(5):
            TaskQueueManager.enqueue_task(db, f"task-{i:03d}", {}, {})

        tasks = TaskQueueManager.list_tasks(db, limit=3)

        assert len(tasks) == 3
