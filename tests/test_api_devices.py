"""Tests for device API endpoints."""

import pytest
from fastapi import status

from omni_server.models import DeviceHeartbeatDB, RunnerStatus


class TestReceiveHeartbeat:
    """Test POST /api/v1/devices/{device_id}/heartbeat endpoint."""

    def test_receive_heartbeat_new_device(self, client, sample_heartbeat):
        """Test receiving heartbeat from a new device."""
        response = client.post("/api/v1/devices/device-001/heartbeat", json=sample_heartbeat)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"

    def test_receive_heartbeat_existing_device(self, client, sample_heartbeat):
        """Test receiving heartbeat update from existing device."""
        # Create initial heartbeat
        response = client.post("/api/v1/devices/device-001/heartbeat", json=sample_heartbeat)
        assert response.status_code == status.HTTP_200_OK

        # Send updated heartbeat
        updated_heartbeat = sample_heartbeat.copy()
        updated_heartbeat["type"] = "running"
        updated_heartbeat["current_task_id"] = "task-001"

        response = client.post("/api/v1/devices/device-001/heartbeat", json=updated_heartbeat)

        assert response.status_code == status.HTTP_200_OK

    def test_receive_heartbeat_mismatched_device_id(self, client, sample_heartbeat):
        """Test receiving heartbeat with mismatched device_id in path and body."""
        response = client.post("/api/v1/devices/device-001/heartbeat", json=sample_heartbeat)

        # The sample_heartbeat has device_id "device-001", so this should fail if they mismatch
        mismatched_heartbeat = sample_heartbeat.copy()
        mismatched_heartbeat["device_id"] = "device-002"

        response = client.post("/api/v1/devices/device-001/heartbeat", json=mismatched_heartbeat)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not match" in response.json()["detail"].lower()


class TestGetDevice:
    """Test GET /api/v1/devices/{device_id} endpoint."""

    def test_get_existing_device(self, client, sample_heartbeat):
        """Test getting an existing device."""
        # Create device first
        device_heartbeat = sample_heartbeat.copy()
        device_heartbeat["type"] = "running"
        device_heartbeat["current_task_id"] = "task-001"
        device_heartbeat["current_task_progress"] = 50.0

        client.post("/api/v1/devices/device-001/heartbeat", json=device_heartbeat)

        response = client.get("/api/v1/devices/device-001")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["device_id"] == "device-001"
        assert data["status"] == "running"
        assert data["runner_version"] == "0.1.0"
        assert data["current_task_progress"] == 50.0

    def test_get_nonexistent_device(self, client):
        """Test getting a device that doesn't exist."""
        response = client.get("/api/v1/devices/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


class TestListDevices:
    """Test GET /api/v1/devices endpoint."""

    def test_list_all_devices(self, client, sample_heartbeat):
        """Test listing all registered devices."""
        # Create multiple devices
        for i in range(3):
            device_heartbeat = sample_heartbeat.copy()
            device_heartbeat["device_id"] = f"device-{i:03d}"
            client.post(f"/api/v1/devices/device-{i:03d}/heartbeat", json=device_heartbeat)

        response = client.get("/api/v1/devices")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

    def test_list_devices_by_status(self, client, sample_heartbeat):
        """Test listing devices filtered by status."""
        # Create devices with different statuses
        idle_heartbeat = sample_heartbeat.copy()
        idle_heartbeat["device_id"] = "idle-device"

        running_heartbeat = sample_heartbeat.copy()
        running_heartbeat["device_id"] = "running-device"
        running_heartbeat["type"] = "running"

        client.post("/api/v1/devices/idle-device/heartbeat", json=idle_heartbeat)
        client.post("/api/v1/devices/running-device/heartbeat", json=running_heartbeat)

        response = client.get("/api/v1/devices?status=running")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["device_id"] == "running-device"
        assert data[0]["status"] == "running"

    def test_list_devices_no_filter(self, client):
        """Test listing devices with no status filter."""
        response = client.get("/api/v1/devices")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)


class TestDeviceHeartbeatFlow:
    """Test complete device heartbeat workflow."""

    def test_complete_heartbeat_flow(self, client, sample_heartbeat):
        """Test the complete flow of device heartbeat lifecycle."""
        # Step 1: Device registers with initial heartbeat
        device_heartbeat = sample_heartbeat.copy()
        device_heartbeat["device_id"] = "device-flow"

        response = client.post("/api/v1/devices/device-flow/heartbeat", json=device_heartbeat)
        assert response.status_code == status.HTTP_200_OK

        # Step 2: Verify device exists
        response = client.get("/api/v1/devices/device-flow")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "idle"
        assert data["current_task_id"] is None

        # Step 3: Device starts running a task
        running_heartbeat = sample_heartbeat.copy()
        running_heartbeat["device_id"] = "device-flow"
        running_heartbeat["type"] = "running"
        running_heartbeat["current_task_id"] = "task-001"
        running_heartbeat["current_task_progress"] = 0.0

        response = client.post("/api/v1/devices/device-flow/heartbeat", json=running_heartbeat)
        assert response.status_code == status.HTTP_200_OK

        # Step 4: Verify device status updated
        response = client.get("/api/v1/devices/device-flow")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "running"
        assert data["current_task_id"] == "task-001"

        # Step 5: Device completes task
        completed_heartbeat = sample_heartbeat.copy()
        completed_heartbeat["device_id"] = "device-flow"
        completed_heartbeat["type"] = "idle"
        completed_heartbeat["current_task_id"] = None
        completed_heartbeat["current_task_progress"] = 100.0

        response = client.post("/api/v1/devices/device-flow/heartbeat", json=completed_heartbeat)
        assert response.status_code == status.HTTP_200_OK

        # Step 6: Verify device back to idle
        response = client.get("/api/v1/devices/device-flow")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "idle"
        assert data["current_task_id"] is None
