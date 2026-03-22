"""OAuth validation tests - sync, no external dependencies."""

import pytest
from urllib.parse import urlparse, parse_qs
from fastapi.testclient import TestClient
from pydantic import ValidationError

from omni_server.main import app
from omni_server.config import Settings


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestOAuthURLValidation:
    """Test OAuth redirect URL generation."""

    def test_github_oauth_url_structure(self, client: TestClient):
        """Test GitHub OAuth redirect URL has correct structure."""
        response = client.get("/api/auth/oauth/github?request_url=http://localhost")
        assert response.status_code == 200

        data = response.json()
        assert "redirect_url" in data

        redirect_url = data["redirect_url"]
        parsed = urlparse(redirect_url)

        # Verify URL uses GitHub OAuth endpoint
        assert parsed.netloc == "github.com"
        assert parsed.path == "/login/oauth/authorize"

        # Verify required query parameters
        params = parse_qs(parsed.query)
        assert "state" in params
        assert "redirect_uri" in params
        assert "scope" in params

    def test_github_oauth_url_has_required_scope(self, client: TestClient):
        """Test GitHub OAuth URL includes required scope."""
        response = client.get("/api/auth/oauth/github?request_url=http://localhost")
        assert response.status_code == 200

        data = response.json()
        redirect_url = data["redirect_url"]
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)

        assert params["scope"] == ["user:email"]

    def test_github_oauth_state_token_present(self, client: TestClient):
        """Test GitHub OAuth URL includes state token for CSRF protection."""
        response = client.get("/api/auth/oauth/github?request_url=http://localhost")
        assert response.status_code == 200

        data = response.json()
        redirect_url = data["redirect_url"]
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)

        # State token should be present
        assert "state" in params
        # State should not be empty (in production, should be random)
        assert params["state"]

    def test_gitlab_oauth_url_structure(self, client: TestClient):
        """Test GitLab OAuth redirect URL has correct structure."""
        response = client.get("/api/auth/oauth/gitlab?request_url=http://localhost")
        assert response.status_code == 200

        data = response.json()
        assert "redirect_url" in data

        redirect_url = data["redirect_url"]
        parsed = urlparse(redirect_url)

        # Verify URL uses GitLab OAuth endpoint
        assert parsed.netloc == "gitlab.com"
        assert parsed.path == "/oauth/authorize"

        # Verify required query parameters
        params = parse_qs(parsed.query)
        assert "state" in params
        assert "redirect_uri" in params
        assert "scope" in params
        assert "response_type" in params
        assert params["response_type"] == ["code"]

    def test_gitlab_oauth_url_has_correct_scope(self, client: TestClient):
        """Test GitLab OAuth URL includes correct scope."""
        response = client.get("/api/auth/oauth/gitlab?request_url=http://localhost")
        assert response.status_code == 200

        data = response.json()
        redirect_url = data["redirect_url"]
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)

        assert params["scope"] == ["read_user"]


class TestOAuthCallbackValidation:
    """Test OAuth callback validation."""

    def test_github_callback_missing_state(self, client: TestClient):
        """Test GitHub callback without state parameter raises 400."""
        response = client.get("/api/auth/oauth/github/callback?code=test_code&state=")
        assert response.status_code == 400
        assert "Invalid state parameter" in response.json()["detail"]

    def test_github_callback_missing_code(self, client: TestClient):
        response = client.get("/api/auth/oauth/github/callback?state=test_state&state=")
        assert response.status_code in [400, 422]

    def test_gitlab_callback_missing_state(self, client: TestClient):
        response = client.get("/api/auth/oauth/gitlab/callback?code=test_code")
        assert response.status_code in [400, 422]

    def test_gitlab_callback_missing_code(self, client: TestClient):
        response = client.get("/api/auth/oauth/gitlab/callback?state=test_state&state=")
        assert response.status_code in [400, 422]


class TestTaskE2E:
    """Task end-to-end workflow tests (sync, no external dependencies)."""

    def test_complete_task_workflow(self, client: TestClient, db_session):
        """Test complete task workflow: create -> assign -> complete."""
        # Import here to avoid circular imports at module level
        from omni_server.models import TaskQueueDB
        from omni_server.config import Settings

        # Create task
        task_manifest = {
            "schema_version": "1.0.0",
            "task_id": "test_task_complete",
            "created_at": "2026-03-21T00:00:00Z",
            "device_binding": {"device_id": "test_device_1", "device_type": "test"},
            "priority": "high",
            "timeout_seconds": 300,
            "pipeline": [
                {
                    "step_id": "step1",
                    "order": 1,
                    "type": "shell",
                    "cmd": "echo test",
                    "env": {},
                    "must_pass": True,
                    "depends_on": [],
                    "always_run": False,
                    "security_policy": {},
                    "timeout_seconds": 60,
                    "artifact_collection": None,
                }
            ],
        }

        # Step 1: Create task
        create_response = client.post("/api/v1/tasks", json=task_manifest)
        assert create_response.status_code == 201
        assert create_response.json()["task_id"] == "test_task_complete"
        assert create_response.json()["status"] == "pending"

        # Step 2: Get task
        get_response = client.get("/api/v1/tasks/test_task_complete")
        assert get_response.status_code == 200
        task_data = get_response.json()
        assert task_data["task_id"] == "test_task_complete"
        assert task_data["status"] == "pending"

        # Step 3: Assign task to device
        assign_response = client.put(
            "/api/v1/tasks/test_task_complete/assign", json={"device_id": "test_device_1"}
        )
        assert assign_response.status_code == 200

        # Step 4: Upload result
        result = {
            "schema_version": "1.0.0",
            "task_id": "test_task_complete",
            "status": "success",
            "started_at": "2026-03-21T00:00:00Z",
            "completed_at": "2026-03-21T00:01:00Z",
            "duration_seconds": 60.0,
            "device_info": {
                "device_id": "test_device_1",
                "hostname": "test-host",
                "runner_version": "0.1.0",
            },
            "steps": [
                {
                    "step_id": "step1",
                    "type": "success",
                    "status": "success",
                    "cmd": "echo test",
                    "exit_code": 0,
                    "started_at": "2026-03-21T00:00:00Z",
                    "completed_at": "2026-03-21T00:00:30Z",
                    "duration_seconds": 30.0,
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
                "total_log_lines": 0,
            },
        }

        upload_response = client.post("/api/v1/tasks/test_task_complete/result", json=result)
        assert upload_response.status_code == 200

        # Step 5: Verify task status updated
        final_response = client.get("/api/v1/tasks/test_task_complete")
        assert final_response.status_code == 200
        final_data = final_response.json()
        assert final_data["status"] == "success"
        assert "result" in final_data
        assert final_data["result"]["status"] == "success"

    def test_task_with_device_registration(self, client: TestClient):
        """Test task workflow with device registration."""
        # Step 1: Register device via heartbeat
        heartbeat = {
            "device_id": "test_device_2",
            "runner_version": "0.1.0",
            "status": "idle",
            "current_task_id": None,
            "current_task_progress": 0.0,
            "system_resources": {
                "cpu_percent": 10.0,
                "memory_used_mb": 512,
                "memory_total_mb": 4096,
                "disk_used_gb": 20,
                "disk_total_gb": 100,
            },
            "capabilities": {
                "supported_step_types": ["shell", "python"],
                "has_oob_capture": False,
                "has_gpu": False,
                "oob_methods": [],
            },
            "last_report": "2026-03-21T00:00:00Z",
        }

        heartbeat_response = client.post("/api/v1/devices/test_device_2/heartbeat", json=heartbeat)
        assert heartbeat_response.status_code in [200, 201]

        # Step 2: Create and assign task
        task_manifest = {
            "schema_version": "1.0.0",
            "task_id": "test_task_with_device",
            "created_at": "2026-03-21T00:00:00Z",
            "device_binding": {
                "device_id": "test_device_2",
                "device_type": "test",
            },
            "priority": "normal",
            "timeout_seconds": 300,
            "pipeline": [
                {
                    "step_id": "step1",
                    "order": 1,
                    "type": "shell",
                    "cmd": "echo device_test",
                    "env": {},
                    "must_pass": True,
                    "depends_on": [],
                    "always_run": False,
                    "security_policy": {},
                    "timeout_seconds": 60,
                    "artifact_collection": None,
                }
            ],
        }

        create_response = client.post("/api/v1/tasks", json=task_manifest)
        assert create_response.status_code == 201

        # Step 3: Assign task to registered device
        assign_response = client.put(
            "/api/v1/tasks/test_task_with_device/assign", json={"device_id": "test_device_2"}
        )
        assert assign_response.status_code == 200

        # Step 3.5: Device heartbeat to confirm task assignment
        assigned_heartbeat = heartbeat.copy()
        assigned_heartbeat["current_task_id"] = "test_task_with_device"
        assigned_heartbeat["status"] = "running"
        assigned_heartbeat["last_report"] = "2026-03-21T00:00:10Z"
        client.post("/api/v1/devices/test_device_2/heartbeat", json=assigned_heartbeat)

        # Step 4: Verify device has assigned task
        device_response = client.get("/api/v1/devices/test_device_2")
        assert device_response.status_code == 200
        device_data = device_response.json()
        assert device_data["current_task_id"] == "test_task_with_device"

        # Step 5: Upload result and verify device freed
        result = {
            "schema_version": "1.0.0",
            "task_id": "test_task_with_device",
            "status": "success",
            "started_at": "2026-03-21T00:00:00Z",
            "completed_at": "2026-03-21T00:01:00Z",
            "duration_seconds": 60.0,
            "device_info": {
                "device_id": "test_device_2",
                "hostname": "test-host",
                "runner_version": "0.1.0",
            },
            "steps": [],
            "summary": {
                "total_steps": 1,
                "successful_steps": 1,
                "failed_steps": 0,
                "skipped_steps": 0,
                "crashed_steps": 0,
                "total_duration_seconds": 60.0,
                "total_artifacts": 0,
                "total_log_lines": 0,
            },
        }

        upload_response = client.post("/api/v1/tasks/test_task_with_device/result", json=result)
        assert upload_response.status_code == 200

        # Device heartbeat to release task
        idle_heartbeat = heartbeat.copy()
        idle_heartbeat["current_task_id"] = None
        idle_heartbeat["status"] = "idle"
        idle_heartbeat["last_report"] = "2026-03-21T00:01:10Z"
        client.post("/api/v1/devices/test_device_2/heartbeat", json=idle_heartbeat)

        # Verify device status updated
        device_final_response = client.get("/api/v1/devices/test_device_2")
        device_final_data = device_final_response.json()
        assert device_final_data["current_task_id"] is None

    def test_task_queue_listing_and_filtering(self, client: TestClient, db_session):
        """Test task queue listing and filtering."""
        # Create multiple tasks with different priorities
        for i in range(5):
            task_manifest = {
                "schema_version": "1.0.0",
                "task_id": f"priority_test_{i}",
                "created_at": "2026-03-21T00:00:00Z",
                "device_binding": {"device_id": f"device_{i}", "device_type": "test"},
                "priority": ["critical", "high", "normal", "normal", "low"][i],
                "timeout_seconds": 300,
                "pipeline": [
                    {
                        "step_id": "step1",
                        "order": 1,
                        "type": "shell",
                        "cmd": "echo test",
                        "env": {},
                        "must_pass": True,
                        "depends_on": [],
                        "always_run": False,
                        "security_policy": {},
                        "timeout_seconds": 60,
                        "artifact_collection": None,
                    }
                ],
            }

            client.post("/api/v1/tasks", json=task_manifest)

        # Test listing all tasks
        all_tasks_response = client.get("/api/v1/tasks")
        assert all_tasks_response.status_code == 200
        all_tasks = all_tasks_response.json()
        assert len(all_tasks) == 5

        # Test filter by status
        pending_tasks = client.get("/api/v1/tasks?status=pending")
        assert pending_tasks.status_code == 200
        pending_list = pending_tasks.json()
        assert len(pending_list) == 5

        client.put("/api/v1/tasks/priority_test_0/assign", json={"device_id": "device_0"})

        # Test status filter
        assigned_tasks = client.get("/api/v1/tasks?status=assigned")
        assert assigned_tasks.status_code == 200
        assigned_list = assigned_tasks.json()
        assert len(assigned_list) == 1

    def test_task_timeout_handling(self, client: TestClient):
        """Test task timeout scenario."""
        task_manifest = {
            "schema_version": "1.0.0",
            "task_id": "test_timeout_task",
            "created_at": "2026-03-21T00:00:00Z",
            "device_binding": {"device_id": "test_device", "device_type": "test"},
            "priority": "high",
            "timeout_seconds": 10,  # Very short timeout for test
            "pipeline": [
                {
                    "step_id": "timeout_step",
                    "order": 1,
                    "type": "shell",
                    "cmd": "sleep 20",
                    "env": {},
                    "must_pass": True,
                    "depends_on": [],
                    "always_run": False,
                    "security_policy": {},
                    "timeout_seconds": 5,
                    "artifact_collection": None,
                }
            ],
        }

        create_response = client.post("/api/v1/tasks", json=task_manifest)
        assert create_response.status_code == 201

        # Assign task
        client.put("/api/v1/tasks/test_timeout_task/assign", json={"device_id": "test_device"})

        # Simulate timeout result
        timeout_result = {
            "schema_version": "1.0.0",
            "task_id": "test_timeout_task",
            "status": "timeout",
            "started_at": "2026-03-21T00:00:00Z",
            "completed_at": "2026-03-21T00:00:05Z",
            "duration_seconds": 5.0,
            "device_info": {
                "device_id": "test_device",
                "hostname": "test-host",
                "runner_version": "0.1.0",
            },
            "steps": [
                {
                    "step_id": "timeout_step",
                    "type": "timeout",
                    "status": "timeout",
                    "cmd": "sleep 20",
                    "exit_code": None,
                    "started_at": "2026-03-21T00:00:00Z",
                    "completed_at": "2026-03-21T00:00:05Z",
                    "duration_seconds": 5.0,
                }
            ],
            "summary": {
                "total_steps": 1,
                "successful_steps": 0,
                "failed_steps": 0,
                "skipped_steps": 0,
                "crashed_steps": 0,
                "total_duration_seconds": 5.0,
                "total_artifacts": 0,
                "total_log_lines": 0,
            },
        }

        upload_response = client.post("/api/v1/tasks/test_timeout_task/result", json=timeout_result)
        assert upload_response.status_code == 200

        # Verify task status
        final_response = client.get("/api/v1/tasks/test_timeout_task")
        assert final_response.status_code == 200
        assert final_response.json()["status"] == "timeout"


class TestDeviceTaskIntegration:
    """Test device-task coordination."""

    def test_device_status_updates_during_task_execution(self, client: TestClient):
        """Test device status synchronization with task status."""
        # Register device
        heartbeat = {
            "device_id": "test_device_sync",
            "runner_version": "0.1.0",
            "status": "idle",
            "current_task_id": None,
            "current_task_progress": 0.0,
            "system_resources": {
                "cpu_percent": 10.0,
                "memory_used_mb": 512,
                "memory_total_mb": 4096,
                "disk_used_gb": 20,
                "disk_total_gb": 100,
            },
            "capabilities": {
                "supported_step_types": ["shell"],
                "has_oob_capture": False,
                "has_gpu": False,
                "oob_methods": [],
            },
            "last_report": "2026-03-21T00:00:00Z",
        }

        client.post("/api/v1/devices/test_device_sync/heartbeat", json=heartbeat)

        # Create and assign task
        task_manifest = {
            "schema_version": "1.0.0",
            "task_id": "test_sync_task",
            "created_at": "2026-03-21T00:00:00Z",
            "device_binding": {"device_id": "test_device_sync", "device_type": "test"},
            "priority": "high",
            "timeout_seconds": 300,
            "pipeline": [],
        }

        client.post("/api/v1/tasks", json=task_manifest)
        client.put("/api/v1/tasks/test_sync_task/assign", json={"device_id": "test_device_sync"})

        # Device heartbeat to confirm task assignment
        assigned_heartbeat = heartbeat.copy()
        assigned_heartbeat["current_task_id"] = "test_sync_task"
        assigned_heartbeat["status"] = "running"
        assigned_heartbeat["last_report"] = "2026-03-21T00:00:10Z"
        client.post("/api/v1/devices/test_device_sync/heartbeat", json=assigned_heartbeat)

        device_response = client.get("/api/v1/devices/test_device_sync")
        assert device_response.status_code == 200
        device_data = device_response.json()
        assert device_data["current_task_id"] == "test_sync_task"

        running_heartbeat = heartbeat.copy()
        running_heartbeat["status"] = "running"
        running_heartbeat["current_task_progress"] = 50.0
        running_heartbeat["last_report"] = "2026-03-21T00:01:00Z"

        client.post("/api/v1/devices/test_device_sync/heartbeat", json=running_heartbeat)

        # Verify progress updated
        device_progress_response = client.get("/api/v1/devices/test_device_sync")
        device_progress_data = device_progress_response.json()
        assert device_progress_data["current_task_progress"] == 50.0
        assert device_progress_data["status"] == "running"

        # Complete task
        result = {
            "schema_version": "1.0.0",
            "task_id": "test_sync_task",
            "status": "success",
            "started_at": "2026-03-21T00:00:00Z",
            "completed_at": "2026-03-21T00:02:00Z",
            "duration_seconds": 120.0,
            "device_info": {
                "device_id": "test_device_sync",
                "hostname": "test-host",
                "runner_version": "0.1.0",
            },
            "steps": [],
            "summary": {
                "total_steps": 0,
                "successful_steps": 0,
                "failed_steps": 0,
                "skipped_steps": 0,
                "crashed_steps": 0,
                "total_duration_seconds": 120.0,
                "total_artifacts": 0,
                "total_log_lines": 0,
            },
        }

        client.post("/api/v1/tasks/test_sync_task/result", json=result)

        # Verify device is idle again
        idle_heartbeat = heartbeat.copy()
        idle_heartbeat["current_task_id"] = None
        idle_heartbeat["current_task_progress"] = 100.0
        idle_heartbeat["last_report"] = "2026-03-21T00:02:00Z"

        client.post("/api/v1/devices/test_device_sync/heartbeat", json=idle_heartbeat)

        final_device_response = client.get("/api/v1/devices/test_device_sync")
        final_device_data = final_device_response.json()
        assert final_device_data["status"] == "idle"
        assert final_device_data["current_task_id"] is None

    def test_device_release_after_task_completion(self, client: TestClient):
        """Test device is properly released after task completion."""
        # Setup: Register device, create and assign task
        heartbeat = {
            "device_id": "test_device_release",
            "runner_version": "0.1.0",
            "status": "idle",
            "current_task_id": None,
            "current_task_progress": 0.0,
            "system_resources": {
                "cpu_percent": 10.0,
                "memory_used_mb": 512,
                "memory_total_mb": 4096,
                "disk_used_gb": 20,
                "disk_total_gb": 100,
            },
            "capabilities": {
                "supported_step_types": ["shell"],
                "has_oob_capture": False,
                "has_gpu": False,
                "oob_methods": [],
            },
            "last_report": "2026-03-21T00:00:00Z",
        }

        client.post("/api/v1/devices/test_device_release/heartbeat", json=heartbeat)

        task_manifest = {
            "schema_version": "1.0.0",
            "task_id": "task_release_test",
            "created_at": "2026-03-21T00:00:00Z",
            "device_binding": {"device_id": "test_device_release", "device_type": "test"},
            "priority": "high",
            "timeout_seconds": 300,
            "pipeline": [],
        }

        client.post("/api/v1/tasks", json=task_manifest)
        client.put(
            "/api/v1/tasks/task_release_test/assign", json={"device_id": "test_device_release"}
        )

        # Device heartbeat to confirm task assignment
        assigned_heartbeat = heartbeat.copy()
        assigned_heartbeat["current_task_id"] = "task_release_test"
        assigned_heartbeat["status"] = "running"
        assigned_heartbeat["last_report"] = "2026-03-21T00:00:10Z"
        client.post("/api/v1/devices/test_device_release/heartbeat", json=assigned_heartbeat)

        # Device should have assigned task
        device_with_task = client.get("/api/v1/devices/test_device_release")
        assert device_with_task.status_code == 200
        assert device_with_task.json()["current_task_id"] == "task_release_test"

        # Complete task
        result = {
            "schema_version": "1.0.0",
            "task_id": "task_release_test",
            "status": "success",
            "started_at": "2026-03-21T00:00:00Z",
            "completed_at": "2026-03-21T00:01:00Z",
            "duration_seconds": 60.0,
            "device_info": {
                "device_id": "test_device_release",
                "hostname": "test-host",
                "runner_version": "0.1.0",
            },
            "steps": [],
            "summary": {
                "total_steps": 0,
                "successful_steps": 0,
                "failed_steps": 0,
                "skipped_steps": 0,
                "crashed_steps": 0,
                "total_duration_seconds": 60.0,
                "total_artifacts": 0,
                "total_log_lines": 0,
            },
        }

        client.post("/api/v1/tasks/task_release_test/result", json=result)

        # Device heartbeat to release task
        idle_heartbeat = heartbeat.copy()
        idle_heartbeat["current_task_id"] = None
        idle_heartbeat["status"] = "idle"
        idle_heartbeat["last_report"] = "2026-03-21T00:01:10Z"
        client.post("/api/v1/devices/test_device_release/heartbeat", json=idle_heartbeat)

        # Device should be released
        device_released = client.get("/api/v1/devices/test_device_release")
        assert device_released.status_code == 200
        device_data = device_released.json()
        assert device_data["current_task_id"] is None

    def test_multiple_tasks_same_device(self, client: TestClient):
        """Test device handling multiple sequential tasks."""
        heartbeat = {
            "device_id": "device_multi_task",
            "runner_version": "0.1.0",
            "status": "idle",
            "current_task_id": None,
            "current_task_progress": 0.0,
            "system_resources": {
                "cpu_percent": 10.0,
                "memory_used_mb": 512,
                "memory_total_mb": 4096,
                "disk_used_gb": 20,
                "disk_total_gb": 100,
            },
            "capabilities": {
                "supported_step_types": ["shell"],
                "has_oob_capture": False,
                "has_gpu": False,
                "oob_methods": [],
            },
            "last_report": "2026-03-21T00:00:00Z",
        }

        client.post("/api/v1/devices/device_multi_task/heartbeat", json=heartbeat)

        # Create and execute first task
        task1_manifest = {
            "schema_version": "1.0.0",
            "task_id": "multi_task_1",
            "created_at": "2026-03-21T00:00:00Z",
            "device_binding": {"device_id": "device_multi_task", "device_type": "test"},
            "priority": "high",
            "timeout_seconds": 300,
            "pipeline": [],
        }

        client.post("/api/v1/tasks", json=task1_manifest)
        client.put("/api/v1/tasks/multi_task_1/assign", json={"device_id": "device_multi_task"})

        # Device heartbeat to confirm task assignment
        assigned_heartbeat1 = heartbeat.copy()
        assigned_heartbeat1["current_task_id"] = "multi_task_1"
        assigned_heartbeat1["status"] = "running"
        assigned_heartbeat1["last_report"] = "2026-03-21T00:00:10Z"
        client.post("/api/v1/devices/device_multi_task/heartbeat", json=assigned_heartbeat1)

        result1 = {
            "schema_version": "1.0.0",
            "task_id": "multi_task_1",
            "status": "success",
            "started_at": "2026-03-21T00:00:00Z",
            "completed_at": "2026-03-21T00:01:00Z",
            "duration_seconds": 60.0,
            "device_info": {
                "device_id": "device_multi_task",
                "hostname": "test-host",
                "runner_version": "0.1.0",
            },
            "steps": [],
            "summary": {
                "total_steps": 0,
                "successful_steps": 0,
                "failed_steps": 0,
                "skipped_steps": 0,
                "crashed_steps": 0,
                "total_duration_seconds": 60.0,
                "total_artifacts": 0,
                "total_log_lines": 0,
            },
        }

        client.post("/api/v1/tasks/multi_task_1/result", json=result1)

        # Device heartbeat to release task
        idle_heartbeat1 = heartbeat.copy()
        idle_heartbeat1["current_task_id"] = None
        idle_heartbeat1["status"] = "idle"
        idle_heartbeat1["last_report"] = "2026-03-21T00:01:10Z"
        client.post("/api/v1/devices/device_multi_task/heartbeat", json=idle_heartbeat1)

        # Verify device is released
        device_after_task1 = client.get("/api/v1/devices/device_multi_task")
        assert device_after_task1.json()["current_task_id"] is None

        # Create and execute second task on same device
        task2_manifest = {
            "schema_version": "1.0.0",
            "task_id": "multi_task_2",
            "created_at": "2026-03-21T00:02:00Z",
            "device_binding": {"device_id": "device_multi_task", "device_type": "test"},
            "priority": "normal",
            "timeout_seconds": 300,
            "pipeline": [],
        }

        client.post("/api/v1/tasks", json=task2_manifest)
        client.put("/api/v1/tasks/multi_task_2/assign", json={"device_id": "device_multi_task"})

        # Device heartbeat to confirm task assignment
        assigned_heartbeat2 = heartbeat.copy()
        assigned_heartbeat2["current_task_id"] = "multi_task_2"
        assigned_heartbeat2["status"] = "running"
        assigned_heartbeat2["last_report"] = "2026-03-21T00:02:10Z"
        client.post("/api/v1/devices/device_multi_task/heartbeat", json=assigned_heartbeat2)

        result2 = {
            "schema_version": "1.0.0",
            "task_id": "multi_task_2",
            "status": "success",
            "started_at": "2026-03-21T00:02:00Z",
            "completed_at": "2026-03-21T00:03:00Z",
            "duration_seconds": 60.0,
            "device_info": {
                "device_id": "device_multi_task",
                "hostname": "test-host",
                "runner_version": "0.1.0",
            },
            "steps": [],
            "summary": {
                "total_steps": 0,
                "successful_steps": 0,
                "failed_steps": 0,
                "skipped_steps": 0,
                "crashed_steps": 0,
                "total_duration_seconds": 60.0,
                "total_artifacts": 0,
                "total_log_lines": 0,
            },
        }

        client.post("/api/v1/tasks/multi_task_2/result", json=result2)

        # Device heartbeat to release task
        idle_heartbeat2 = heartbeat.copy()
        idle_heartbeat2["current_task_id"] = None
        idle_heartbeat2["status"] = "idle"
        idle_heartbeat2["last_report"] = "2026-03-21T00:03:10Z"
        client.post("/api/v1/devices/device_multi_task/heartbeat", json=idle_heartbeat2)

        # Verify device is released again
        device_after_task2 = client.get("/api/v1/devices/device_multi_task")
        assert device_after_task2.json()["current_task_id"] is None
        assert device_after_task2.json()["status"] == "idle"
