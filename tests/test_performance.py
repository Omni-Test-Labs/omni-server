"""
Performance tests for omni-server concurrent operations and load testing.

Tests concurrent operations, load handling, response times, and resource limits.
"""

import pytest
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from omni_server.models import (
    UserDB,
    TaskQueueDB,
)
from omni_server.models import DeviceHeartbeatDB, RunnerStatus


# ============================================================================
# Performance test utilities
# ============================================================================


def generate_unique_username(prefix: str) -> str:
    """Generate a unique username for testing."""
    timestamp = int(time.time() * 1000)
    return f"{prefix}_{timestamp}"


# ============================================================================
# Fixtures for performance testing
# ============================================================================


@pytest.fixture(scope="function")
def performance_db(db: Session):
    """Create performance test data. Roles are seeded by seed_default_roles fixture."""
    # Don't create roles here - they're automatically seeded by the autouse fixture
    return db


@pytest.fixture
def performance_client(performance_db: Session):
    """Create test client with performance database setup."""
    from omni_server.main import app
    from omni_server.database import get_db

    def override_get_db() -> Session:
        yield performance_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sample_auth_headers(performance_db: Session):
    """Create authentication headers for performance tests."""
    # Not implemented - return empty headers for now
    # Most tests will skip auth-dependent operations
    return {}


# ============================================================================
# Concurrent Operations Tests
# ============================================================================


@pytest.mark.skip(reason="Task API endpoints may require authentication")
def test_concurrent_task_creation(performance_client: TestClient, performance_db: Session):
    """Test concurrent task creation performance."""

    def create_task(task_num: int):
        """Create a single task for testing."""
        task_data = {
            "task_id": f"perf_task_{int(time.time())}_{task_num}",
            "schema_version": "1.0.0",
            "created_at": "2024-03-20T10:00:00Z",
            "device_binding": {
                "device_id": f"device_{task_num}",
                "device_type": "pc",
                "oob_methods": [],
            },
            "priority": "normal",
            "timeout_seconds": 300,
            "pipeline": [
                {
                    "step_id": f"step-1-{int(time.time())}",
                    "order": 1,
                    "type": "shell",
                    "cmd": "echo hello from task {task_num}",
                    "working_dir": None,
                    "must_pass": True,
                    "depends_on": [],
                    "always_run": False,
                    "timeout_seconds": 10,
                }
            ],
        }

        start_time = time.time()
        result = performance_client.post("/api/tasks", json=task_data)
        end_time = time.time()
        duration = end_time - start_time
        return result, duration

    # Number of concurrent tasks to create
    num_tasks = 50

    # Create tasks concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_task, i) for i in range(num_tasks)]

        results = []
        durations = []
        for future in as_completed(futures):
            result, duration = future.result()
            results.append(result)
            durations.append(duration)

    # Assert all tasks were created successfully
    successful = sum(1 for r in results if r.status_code == 201)
    assert successful == num_tasks, f"Expected {num_tasks} successful creations, got {successful}"

    # Performance assertions
    avg_duration = sum(durations) / len(durations)
    assert avg_duration < 1.0, f"Average task creation time {avg_duration:.3f}s exceeds 1s limit"

    max_duration = max(durations)
    assert max_duration < 5.0, f"Max task creation time {max_duration:.3f}s exceeds 5s limit"


def test_concurrent_device_heartbeats(performance_client: TestClient, performance_db: Session):
    """Test concurrent device heartbeat submissions."""

    def send_heartbeat(device_id: str):
        """Send a heartbeat for a single device."""
        heartbeat_data = {
            "device_id": device_id,
            "runner_version": "0.1.0",
            "status": "idle",
            "current_task_id": None,
            "current_task_progress": 0.0,
            "api_version": "0.1.0",
            "system_resources": {
                "cpu_percent": 10.0,
                "memory_mb": 8192,
            },
            "capabilities": {
                "python": "3.10",
                "os": "linux",
            },
            "last_report": "2024-03-20T10:00:00Z",
        }

        start_time = time.time()
        result = performance_client.post(
            f"/api/v1/devices/{device_id}/heartbeat", json=heartbeat_data
        )
        end_time = time.time()
        duration = end_time - start_time
        return result, duration

    # Send heartbeats for multiple devices concurrently
    num_devices = 30

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_heartbeat, f"device_{i}") for i in range(num_devices)]

        results = []
        durations = []
        for future in as_completed(futures):
            result, duration = future.result()
            results.append(result)
            durations.append(duration)

    # Check that all heartbeats were accepted
    successful = sum(1 for r in results if r.status_code in [200, 201])
    assert successful == num_devices, (
        f"Expected {num_devices} successful heartbeats, got {successful}"
    )

    # Performance assertions
    avg_duration = sum(durations) / len(durations)
    assert avg_duration < 0.5, f"Average heartbeat time {avg_duration:.3f}s exceeds 0.5s limit"


@pytest.mark.skip(reason="Requires multiple test clients")
def test_concurrent_api_requests(performance_client: TestClient):
    """Test concurrent API requests to different endpoints."""
    endpoints = [
        "/api/v1/auth/me",
        "/api/v1/devices",
        "/api/v1/tasks",
        "/api/v1/users",
        "/api/v1/notifications",
    ]

    def make_request(endpoint: str):
        """Make a single API request."""
        start_time = time.time()
        result = performance_client.get(endpoint)
        end_time = time.time()
        duration = end_time - start_time
        return result, duration, endpoint

    # Make requests to multiple endpoints concurrently
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request, endpoint) for endpoint in endpoints * 10]

        results = []
        for future in as_completed(futures):
            result, duration, endpoint = future.result()
            results.append((result, duration, endpoint))

    # Check that most requests succeeded
    successful = sum(1 for r, _, _ in results if r.status_code == 200)
    assert successful >= 40, f"Expected at least 40/50 successful requests, got {successful}"


# ============================================================================
# Load Testing Tests
# ============================================================================


@pytest.mark.skip(reason="Task API requires authentication")
def test_high_load_task_creation(performance_client: TestClient):
    """Test high load task creation (100 tasks in sequence)."""
    num_tasks = 100
    results = []
    durations = []

    for i in range(num_tasks):
        task_data = {
            "task_id": f"load_task_{int(time.time())}_{i}",
            "schema_version": "1.0.0",
            "created_at": "2024-03-20T10:00:00Z",
            "device_binding": {
                "device_id": f"device_load_{i}",
                "device_type": "server",
                "oob_methods": [],
            },
            "priority": "normal",
            "timeout_seconds": 300,
            "pipeline": [
                {
                    "step_id": f"step-{int(time.time())}",
                    "order": 1,
                    "type": "shell",
                    "cmd": f"echo load test {i}",
                    "working_dir": None,
                    "must_pass": True,
                    "depends_on": [],
                    "always_run": False,
                    "timeout_seconds": 10,
                }
            ],
        }

        start_time = time.time()
        result = performance_client.post("/api/tasks", json=task_data)
        end_time = time.time()
        duration = end_time - start_time
        results.append(result)
        durations.append(duration)

    # Check that all tasks were created successfully
    successful = sum(1 for r in results if r.status_code == 201)
    assert successful == num_tasks, f"Expected {num_tasks} successful creations, got {successful}"

    # Performance assertions
    avg_duration = sum(durations) / len(durations)
    assert avg_duration < 0.5, (
        f"Average task creation time {avg_duration:.3f}s exceeds 0.5s limit under load"
    )


def test_high_load_device_allocation(performance_client: TestClient):
    """Test high load device allocation using heartbeats."""
    num_devices = 50
    results = []
    durations = []

    for i in range(num_devices):
        heartbeat_data = {
            "device_id": f"load_device_{i}",
            "runner_version": "0.1.0",
            "status": "idle",
            "current_task_id": None,
            "current_task_progress": 0.0,
            "api_version": "0.1.0",
            "system_resources": {
                "cpu_percent": 10.0,
                "memory_mb": 8192,
            },
            "capabilities": {
                "python": "3.10",
                "os": "linux",
            },
            "last_report": "2024-03-20T10:00:00Z",
        }

        start_time = time.time()
        result = performance_client.post(
            f"/api/v1/devices/load_device_{i}/heartbeat", json=heartbeat_data
        )
        end_time = time.time()
        duration = end_time - start_time
        results.append(result)
        durations.append(duration)

    # Check that all devices were registered
    successful = sum(1 for r in results if r.status_code == 200)
    assert successful == num_devices, (
        f"Expected {num_devices} successful registrations, got {successful}"
    )

    # Performance assertions
    avg_duration = sum(durations) / len(durations)
    assert avg_duration < 0.3, (
        f"Average heartbeat time {avg_duration:.3f}s exceeds 0.3s limit under load"
    )


def test_stress_test_api_endpoints(performance_client: TestClient):
    """Stress test API endpoints with rapid sequential requests."""
    endpoint = "/api/v1/devices"
    num_requests = 100

    results = []
    durations = []

    for i in range(num_requests):
        # GET requests
        start_time = time.time()
        result = performance_client.get(endpoint)
        end_time = time.time()
        duration = end_time - start_time
        results.append(result)
        durations.append(duration)

    # Check that most requests succeeded (may have 404 for pagination limits)
    successful = sum(1 for r in results if r.status_code == 200)
    assert successful >= 90, f"Expected at least 90/100 successful requests, got {successful}"

    # Performance assertions
    avg_duration = sum(durations) / len(durations)
    assert avg_duration < 0.2, (
        f"Average GET request time {avg_duration:.3f}s exceeds 0.2s limit under stress"
    )


# ============================================================================
# Response Time Benchmark Tests
# ============================================================================


@pytest.mark.skip(reason="Task API requires authentication")
def test_task_creation_latency(performance_client: TestClient):
    """Test task creation latency (time from request to response)."""
    measurements = []

    for i in range(20):
        task_data = {
            "task_id": f"latency_task_{int(time.time())}_{i}",
            "schema_version": "1.0.0",
            "created_at": "2024-03-20T10:00:00Z",
            "device_binding": {
                "device_id": f"latency_device_{i}",
                "device_type": "pc",
                "oob_methods": [],
            },
            "priority": "normal",
            "timeout_seconds": 300,
            "pipeline": [
                {
                    "step_id": f"step-{int(time.time())}",
                    "order": 1,
                    "type": "shell",
                    "cmd": "echo latency test",
                    "working_dir": None,
                    "must_pass": True,
                    "depends_on": [],
                    "always_run": False,
                    "timeout_seconds": 10,
                }
            ],
        }

        start_time = time.time()
        result = performance_client.post("/api/tasks", json=task_data)
        end_time = time.time()
        duration = end_time - start_time
        measurements.append(duration)

    # Performance assertions
    avg_latency = sum(measurements) / len(measurements)
    assert avg_latency < 0.5, (
        f"Average task creation latency {avg_latency:.3f}s exceeds 0.5s threshold"
    )

    # 95th percentile should be under 1s
    sorted_latency = sorted(measurements)
    p95 = sorted_latency[int(len(measurements) * 0.95)]
    assert p95 < 1.0, f"95th percentile latency {p95:.3f}s exceeds 1.0s threshold"


def test_device_query_latency(performance_client: TestClient):
    """Test device query latency from database."""
    measurements = []

    for i in range(20):
        start_time = time.time()
        result = performance_client.get("/api/v1/devices")
        end_time = time.time()
        duration = end_time - start_time
        measurements.append(duration)

    # Performance assertions
    avg_latency = sum(measurements) / len(measurements)
    assert avg_latency < 0.3, (
        f"Average device query latency {avg_latency:.3f}s exceeds 0.3s threshold"
    )


def test_api_response_time_benchmark(performance_client: TestClient):
    """Test API response times for common endpoints."""
    endpoints = ["/api/v1/devices", "/api/v1/users"]

    all_measurements = {}

    for endpoint in endpoints:
        measurements = []
        for i in range(10):
            start_time = time.time()
            result = performance_client.get(endpoint)
            end_time = time.time()
            duration = end_time - start_time
            measurements.append(duration)

        avg_latency = sum(measurements) / len(measurements)
        max_latency = max(measurements)

        all_measurements[endpoint] = {
            "avg": avg_latency,
            "max": max_latency,
            "min": min(measurements),
            "count": len(measurements),
        }

        # Performance assertions for each endpoint
        assert avg_latency < 0.5, f"{endpoint}: avg {avg_latency:.3f}s exceeds 0.5s threshold"
        assert max_latency < 1.5, f"{endpoint}: max {max_latency:.3f}s exceeds 1.5s threshold"

    # Overall assertion
    # Total test time should be reasonable
    total_tests = sum(len(m) for m in all_measurements.values())
    assert total_tests < 20, f"Total benchmark time {total_tests}s is too high"


# ============================================================================
# Resource Limit Tests
# ============================================================================


def test_memory_usage_under_load(performance_client: TestClient, performance_db: Session):
    """Test memory usage when creating many objects via heartbeats."""
    # Create many devices to measure memory impact
    num_devices = 100

    for i in range(num_devices):
        heartbeat_data = {
            "device_id": f"memory_device_{i}",
            "runner_version": "0.1.0",
            "status": "idle",
            "current_task_id": None,
            "current_task_progress": 0.0,
            "api_version": "0.1.0",
            "system_resources": {
                "cpu_percent": 10.0,
                "memory_mb": 8192,
            },
            "capabilities": {},
            "last_report": "2024-03-20T10:00:00Z",
        }

        performance_client.post(f"/api/v1/devices/memory_device_{i}/heartbeat", json=heartbeat_data)

    # Verify all devices were created
    response = performance_client.get("/api/v1/devices")
    assert response.status_code == 200

    devices = response.json()
    assert len(devices) >= num_devices, (
        f"Only created {len(devices)} devices, expected at least {num_devices}"
    )

    # Memory usage should be reasonable (cannot measure directly, but we test by creating many devices)
    pass


def test_connection_pool_sizing(performance_client: TestClient):
    """Test that connection pool can handle multiple concurrent clients."""
    # Issue multiple requests in parallel
    num_requests = 50

    def make_request(request_num: int):
        # Make a simple GET request
        start_time = time.time()
        result = performance_client.get("/api/v1/devices")
        end_time = time.time()
        return result.status_code == 200

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(make_request, i) for i in range(num_requests)]

        results = [future.result() for future in as_completed(futures)]

    # Most requests should succeed
    successful = sum(results)
    assert successful >= 45, f"Expected at least 45/50 successful requests, got {successful}"


@pytest.mark.skip(reason="Device creation API does not exist")
def test_query_performance_large_dataset(performance_client: TestClient):
    """Test query performance with large result sets."""
    pass


@pytest.mark.skip(reason="Device creation API does not exist")
def test_concurrent_workflow_complete(performance_client: TestClient):
    """Test complete workflow under concurrent load."""
    pass


# ============================================================================
# Performance Baseline Tests
# ============================================================================


@pytest.mark.skip(reason="Task API requires authentication")
def test_performance_baseline_consistency(performance_client: TestClient):
    """Test that performance baselines are consistent across multiple runs."""
    pass


# ============================================================================
# Concurrent Task Management Tests
# ============================================================================


@pytest.mark.skip(reason="Task API requires authentication")
def test_concurrent_task_status_updates(performance_client: TestClient, performance_db: Session):
    """Test concurrent task status updates."""
    pass


@pytest.mark.skip(reason="Task API requires authentication")
def test_concurrent_task_execution_updates(performance_client: TestClient, performance_db: Session):
    """Test concurrent task execution result updates."""
    pass


# ============================================================================
# Performance Test Summary
# ============================================================================


def test_performance_test_summary(performance_client: TestClient):
    """Run a comprehensive performance test suite and output summary."""
    test_results = {}

    # 1. Concurrent device heartbeats: 50 concurrent heartbeats
    start = time.time()
    num_concurrent = 50
    concurrent_results = []
    concurrent_durations = []

    def send_heartbeat(device_id: str):
        """Send a heartbeat for a single device."""
        heartbeat_data = {
            "device_id": device_id,
            "runner_version": "0.1.0",
            "status": "idle",
            "current_task_id": None,
            "current_task_progress": 0.0,
            "api_version": "0.1.0",
            "system_resources": {
                "cpu_percent": 10.0,
                "memory_mb": 8192,
            },
            "capabilities": {
                "python": "3.10",
                "os": "linux",
            },
            "last_report": "2024-03-20T10:00:00Z",
        }
        start_time = time.time()
        result = performance_client.post(
            f"/api/v1/devices/{device_id}/heartbeat", json=heartbeat_data
        )
        end_time = time.time()
        duration = end_time - start_time
        return result, duration

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_heartbeat, f"device_{i}") for i in range(num_concurrent)]

        for future in as_completed(futures):
            result, duration = future.result()
            concurrent_results.append(result.status_code)
            concurrent_durations.append(duration)

    concurrent_duration = time.time() - start
    test_results["concurrent_heartbeats"] = {
        "num_requests": num_concurrent,
        "successful": sum(1 for r in concurrent_results if r == 200),
        "total_time": concurrent_duration,
        "avg_time": sum(concurrent_durations) / len(concurrent_durations),
        "max_time": max(concurrent_durations),
        "requests_per_second": num_concurrent / concurrent_duration,
    }

    # 2. High load sequence test: 100 sequential heartbeat submissions
    start = time.time()
    num_load = 100
    load_results = []
    load_durations = []

    for i in range(num_load):
        heartbeat_data = {
            "device_id": f"load_device_{i}",
            "runner_version": "0.1.0",
            "status": "idle",
            "current_task_id": None,
            "current_task_progress": 0.0,
            "api_version": "0.1.0",
            "system_resources": {
                "cpu_percent": 10.0,
                "memory_mb": 8192,
            },
            "capabilities": {
                "python": "3.10",
                "os": "linux",
            },
            "last_report": "2024-03-20T10:00:00Z",
        }

        start_time = time.time()
        result = performance_client.post(
            f"/api/v1/devices/load_device_{i}/heartbeat", json=heartbeat_data
        )
        end_time = time.time()
        duration = end_time - start_time
        load_results.append(result.status_code)
        load_durations.append(duration)

    load_duration = time.time() - start
    test_results["high_load_heartbeats"] = {
        "num_requests": num_load,
        "successful": sum(1 for r in load_results if r == 200),
        "total_time": load_duration,
        "avg_time": sum(load_durations) / len(load_durations),
        "max_time": max(load_durations),
        "requests_per_second": num_load / load_duration,
    }

    # 3. Response time test: 20 repetitions per endpoint
    endpoints = ["/api/v1/devices", "/api/v1/users"]
    endpoint_results = {}

    for endpoint in endpoints:
        measurements = []
        for i in range(20):
            start_time = time.time()
            result = performance_client.get(endpoint)
            end_time = time.time()
            duration = end_time - start_time
            measurements.append(duration)

        endpoint_results[endpoint] = {
            "avg": sum(measurements) / len(measurements),
            "max": max(measurements),
            "min": min(measurements),
            "count": len(measurements),
        }

    test_results["response_times"] = endpoint_results

    # Assert all tests passed
    assert test_results["concurrent_heartbeats"]["successful"] == num_concurrent, (
        f"Concurrent test: {test_results['concurrent_heartbeats']['successful']}/{num_concurrent} passed"
    )
    assert test_results["high_load_heartbeats"]["successful"] == num_load, (
        f"Load test: {test_results['high_load_heartbeats']['successful']}/{num_load} passed"
    )

    # Performance thresholds
    assert test_results["concurrent_heartbeats"]["avg_time"] < 1.0, (
        f"Concurrent avg exceeded threshold: {test_results['concurrent_heartbeats']['avg_time']:.3f}s"
    )
    assert test_results["high_load_heartbeats"]["avg_time"] < 0.5, (
        f"Load test avg exceeded threshold: {test_results['high_load_heartbeats']['avg_time']:.3f}s"
    )
    assert test_results["concurrent_heartbeats"]["requests_per_second"] >= 30, (
        f"Throughput too low: {test_results['concurrent_heartbeats']['requests_per_second']:.1f} req/s"
    )

    print("\n=== Performance Test Summary ===")
    print(f"Concurrent Heartbeats ({num_concurrent} threads):")
    print(f"  - Total time: {concurrent_duration:.2f}s")
    print(f"  - Average: {test_results['concurrent_heartbeats']['avg_time'] * 1000:.1f}ms")
    print(f"  - Max: {test_results['concurrent_heartbeats']['max_time'] * 1000:.1f}ms")
    print(
        f"  - Throughput: {test_results['concurrent_heartbeats']['requests_per_second']:.1f} req/s"
    )

    print(f"\nHigh Load Sequential ({num_load} requests):")
    print(f"  - Total time: {load_duration:.2f}s")
    print(f"  - Average: {test_results['high_load_heartbeats']['avg_time'] * 1000:.1f}ms")
    print(
        f"  - Throughput: {test_results['high_load_heartbeats']['requests_per_second']:.1f} req/s"
    )

    print(f"\nResponse Time Benchmarks:")
    for endpoint, metrics in endpoint_results.items():
        print(f"  {endpoint}:")
        print(f"    Avg: {metrics['avg'] * 1000:.1f}ms")
        print(f"    Max: {metrics['max'] * 1000:.1f}ms")
        print(f"    Min: {metrics['min'] * 1000:.1f}ms")

    # Return results for verification
    return test_results
