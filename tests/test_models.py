"""Tests for Pydantic models."""

import pytest

from omni_server.models import (
    DeviceHeartbeatDB,
    ExecutionResult,
    Heartbeat,
    PipelineStep,
    Priority,
    RetryPolicy,
    RunnerStatus,
    SecurityPolicy,
    StepResult,
    StepType,
    Summary,
    TaskManifest,
    TaskQueueDB,
    TaskStatus,
)


class TestEnums:
    """Test enum types."""

    def test_step_type_values(self):
        """Test StepType enum values."""
        assert StepType.python.value == "python"
        assert StepType.binary.value == "binary"
        assert StepType.shell.value == "shell"
        assert StepType.api.value == "api"

    def test_priority_values(self):
        """Test Priority enum values."""
        assert Priority.critical.value == "critical"
        assert Priority.high.value == "high"
        assert Priority.normal.value == "normal"
        assert Priority.low.value == "low"

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.success.value == "success"
        assert TaskStatus.failed.value == "failed"
        assert TaskStatus.crashed.value == "crashed"
        assert TaskStatus.timeout.value == "timeout"
        assert TaskStatus.skipped.value == "skipped"
        assert TaskStatus.pending.value == "pending"
        assert TaskStatus.assigned.value == "assigned"
        assert TaskStatus.running.value == "running"

    def test_runner_status_values(self):
        """Test RunnerStatus enum values."""
        assert RunnerStatus.idle.value == "idle"
        assert RunnerStatus.running.value == "running"
        assert RunnerStatus.offline.value == "offline"


class TestRetryPolicy:
    """Test RetryPolicy model."""

    def test_retry_policy_defaults(self):
        """Test RetryPolicy default values."""
        policy = RetryPolicy()
        assert policy.max_retries == 0
        assert policy.retry_delay_seconds == 5
        assert policy.backoff_multiplier == 2.0

    def test_retry_policy_custom(self):
        """Test RetryPolicy with custom values."""
        policy = RetryPolicy(max_retries=3, retry_delay_seconds=10, backoff_multiplier=1.5)
        assert policy.max_retries == 3
        assert policy.retry_delay_seconds == 10
        assert policy.backoff_multiplier == 1.5

    def test_retry_policy_serialization(self):
        """Test RetryPolicy serialization."""
        policy = RetryPolicy()
        data = policy.model_dump()
        assert data == {"max_retries": 0, "retry_delay_seconds": 5, "backoff_multiplier": 2.0}


class TestSecurityPolicy:
    """Test SecurityPolicy model."""

    def test_security_policy_defaults(self):
        """Test SecurityPolicy default values."""
        policy = SecurityPolicy()
        assert policy.allow_sudo is False
        assert policy.forbidden_cmds == []
        assert policy.allowed_dirs == []

    def test_security_policy_custom(self):
        """Test SecurityPolicy with custom values."""
        policy = SecurityPolicy(
            allow_sudo=True, forbidden_cmds=["rm", "dd"], allowed_dirs=["/tmp", "/home"]
        )
        assert policy.allow_sudo is True
        assert policy.forbidden_cmds == ["rm", "dd"]
        assert policy.allowed_dirs == ["/tmp", "/home"]


class TestPipelineStep:
    """Test PipelineStep model."""

    def test_pipeline_step_minimal(self):
        """Test PipelineStep with minimal required fields."""
        step = PipelineStep(
            step_id="step-1", order=1, type=StepType.shell, cmd="echo hello", timeout_seconds=10
        )
        assert step.step_id == "step-1"
        assert step.order == 1
        assert step.step_type == StepType.shell
        assert step.cmd == "echo hello"
        assert step.env == {}
        assert step.working_dir is None
        assert step.must_pass is True
        assert step.depends_on == []
        assert step.always_run is False
        assert step.timeout_seconds == 10

    def test_pipeline_step_full(self):
        """Test PipelineStep with all fields."""
        step = PipelineStep(
            step_id="step-1",
            order=1,
            type=StepType.shell,
            cmd="echo hello",
            env={"FOO": "bar"},
            working_dir="/tmp",
            must_pass=True,
            depends_on=["step-0"],
            always_run=False,
            retry_policy=RetryPolicy(max_retries=3),
            security_policy=SecurityPolicy(allow_sudo=False),
            timeout_seconds=10,
        )
        assert step.env == {"FOO": "bar"}
        assert step.working_dir == "/tmp"
        assert step.depends_on == ["step-0"]
        assert step.retry_policy.max_retries == 3

    def test_pipeline_step_alias(self):
        """Test PipelineStep alias 'type' for step_type."""
        data = {"step_id": "s1", "order": 1, "type": "shell", "cmd": "ls", "timeout_seconds": 10}
        step = PipelineStep(**data)
        assert step.step_type == StepType.shell


class TestTaskManifest:
    """Test TaskManifest model."""

    def test_task_manifest_minimal(self):
        """Test TaskManifest with minimal fields."""
        manifest = TaskManifest(
            schema_version="1.0.0",
            task_id="task-001",
            created_at="2024-03-18T10:00:00Z",
            device_binding={"device_id": "d1"},
            priority=Priority.normal,
            timeout_seconds=300,
            pipeline=[],
        )
        assert manifest.task_id == "task-001"
        assert manifest.pipeline == []

    def test_task_manifest_with_steps(self):
        """Test TaskManifest with pipeline steps."""
        step = PipelineStep(
            step_id="step-1", order=1, type=StepType.shell, cmd="ls", timeout_seconds=10
        )
        manifest = TaskManifest(
            schema_version="1.0.0",
            task_id="task-001",
            created_at="2024-03-18T10:00:00Z",
            device_binding={"device_id": "d1"},
            priority=Priority.high,
            timeout_seconds=300,
            pipeline=[step],
        )
        assert len(manifest.pipeline) == 1
        assert manifest.pipeline[0].step_id == "step-1"


class TestStepResult:
    """Test StepResult model."""

    def test_step_result_minimal(self):
        """Test StepResult with minimal fields."""
        result = StepResult(step_id="step-1", type=TaskStatus.success)
        assert result.step_id == "step-1"
        assert result.status == TaskStatus.success

    def test_step_result_full(self):
        """Test StepResult with all fields."""
        result = StepResult(
            step_id="step-1",
            type=TaskStatus.failed,
            started_at="2024-03-18T10:00:00Z",
            completed_at="2024-03-18T10:01:00Z",
            duration_seconds=60.0,
            exit_code=1,
        )
        assert result.started_at == "2024-03-18T10:00:00Z"
        assert result.exit_code == 1

    def test_step_result_alias(self):
        """Test StepResult alias 'type' for status."""
        data = {"step_id": "s1", "type": "success"}
        result = StepResult(**data)
        assert result.status == TaskStatus.success


class TestSummary:
    """Test Summary model."""

    def test_summary_fields(self):
        """Test Summary model fields."""
        summary = Summary(
            total_steps=10,
            successful_steps=8,
            failed_steps=1,
            skipped_steps=1,
            crashed_steps=0,
            total_duration_seconds=300.0,
            total_artifacts=5,
            total_log_lines=1000,
        )
        assert summary.total_steps == 10
        assert summary.successful_steps == 8
        assert summary.failed_steps == 1
        assert summary.total_duration_seconds == 300.0


class TestExecutionResult:
    """Test ExecutionResult model."""

    def test_execution_result_minimal(self):
        """Test ExecutionResult with minimal fields."""
        result = ExecutionResult(
            schema_version="1.0.0",
            task_id="task-001",
            type=TaskStatus.success,
            started_at="2024-03-18T10:00:00Z",
            duration_seconds=300.0,
            device_info={"device_id": "d1"},
            steps=[],
            summary=Summary(
                total_steps=0,
                successful_steps=0,
                failed_steps=0,
                skipped_steps=0,
                crashed_steps=0,
                total_duration_seconds=0.0,
                total_artifacts=0,
                total_log_lines=0,
            ),
        )
        assert result.task_id == "task-001"
        assert result.status == TaskStatus.success

    def test_execution_result_alias(self):
        """Test ExecutionResult alias 'type' for status."""
        summary = Summary(
            total_steps=0,
            successful_steps=0,
            failed_steps=0,
            skipped_steps=0,
            crashed_steps=0,
            total_duration_seconds=0.0,
            total_artifacts=0,
            total_log_lines=0,
        )
        data = {
            "schema_version": "1.0.0",
            "task_id": "t1",
            "type": "success",
            "started_at": "2024-03-18T10:00:00Z",
            "duration_seconds": 60.0,
            "device_info": {},
            "steps": [],
            "summary": summary.model_dump(),
        }
        result = ExecutionResult(**data)
        assert result.status == TaskStatus.success


class TestHeartbeat:
    """Test Heartbeat model."""

    def test_heartbeat_minimal(self):
        """Test Heartbeat with minimal fields."""
        heartbeat = Heartbeat(
            device_id="device-001",
            runner_version="0.1.0",
            type=RunnerStatus.idle,
            system_resources={},
            capabilities={},
            last_report="2024-03-18T10:00:00Z",
        )
        assert heartbeat.device_id == "device-001"
        assert heartbeat.status == RunnerStatus.idle
        assert heartbeat.current_task_id is None
        assert heartbeat.current_task_progress == 0.0

    def test_heartbeat_full(self):
        """Test Heartbeat with all fields."""
        heartbeat = Heartbeat(
            device_id="device-001",
            runner_version="0.1.0",
            type=RunnerStatus.running,
            current_task_id="task-001",
            current_task_progress=50.0,
            system_resources={"cpu_percent": 80.0},
            capabilities={"python": "3.10"},
            last_report="2024-03-18T10:00:00Z",
        )
        assert heartbeat.status == RunnerStatus.running
        assert heartbeat.current_task_id == "task-001"
        assert heartbeat.current_task_progress == 50.0

    def test_heartbeat_alias(self):
        """Test Heartbeat alias 'type' for status."""
        data = {
            "device_id": "d1",
            "runner_version": "0.1.0",
            "type": "idle",
            "system_resources": {},
            "capabilities": {},
            "last_report": "2024-03-18T10:00:00Z",
        }
        heartbeat = Heartbeat(**data)
        assert heartbeat.status == RunnerStatus.idle


class TestDatabaseModels:
    """Test SQLAlchemy database models."""

    def test_task_queue_db_creation(self, db):
        """Test TaskQueueDB model creation."""
        task = TaskQueueDB(
            task_id="task-001",
            status="pending",
            priority="normal",
            device_binding={"device_id": "d1"},
            task_manifest={},
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        assert task.task_id == "task-001"
        assert task.status == "pending"

    def test_device_heartbeat_db_creation(self, db):
        """Test DeviceHeartbeatDB model creation."""
        heartbeat = DeviceHeartbeatDB(
            device_id="device-001",
            status="idle",
            system_resources={},
            capabilities={},
            runner_version="0.1.0",
        )
        db.add(heartbeat)
        db.commit()
        db.refresh(heartbeat)

        assert heartbeat.device_id == "device-001"
        assert heartbeat.status == "idle"
        assert heartbeat.current_task_id is None
