"""Data models for tasks, devices, and results matching protocol.md."""

from datetime import datetime
from typing import Any, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class StepType(str, Enum):
    """Type of pipeline step."""

    python = "python"
    binary = "binary"
    shell = "shell"
    api = "api"


class Priority(str, Enum):
    """Task priority level."""

    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class TaskStatus(str, Enum):
    """Task execution status."""

    success = "success"
    failed = "failed"
    crashed = "crashed"
    timeout = "timeout"
    skipped = "skipped"
    pending = "pending"
    assigned = "assigned"
    running = "running"


class RunnerStatus(str, Enum):
    """Runner operational status."""

    idle = "idle"
    running = "running"
    offline = "offline"


class RetryPolicy(BaseModel):
    """Retry policy for a step."""

    max_retries: int = 0
    retry_delay_seconds: int = 5
    backoff_multiplier: float = 2.0


class SecurityPolicy(BaseModel):
    """Security policy for task execution."""

    allow_sudo: bool = False
    forbidden_cmds: list[str] = []
    allowed_dirs: list[str] = []


class PipelineStep(BaseModel):
    """A single step in a task pipeline."""

    step_id: str
    order: int
    step_type: StepType = Field(alias="type")
    cmd: str
    env: dict[str, str] = {}
    working_dir: Optional[str] = None
    must_pass: bool = True
    depends_on: list[str] = []
    always_run: bool = False
    retry_policy: Optional[RetryPolicy] = None
    security_policy: SecurityPolicy = SecurityPolicy()
    timeout_seconds: int

    class Config:
        populate_by_name = True


class TaskManifest(BaseModel):
    """Complete task definition following protocol.md."""

    schema_version: str = "1.0.0"
    task_id: str
    created_at: str
    device_binding: dict[str, Any]
    priority: Priority
    timeout_seconds: int
    pipeline: list[PipelineStep]


class StepResult(BaseModel):
    """Result of executing a single step."""

    step_id: str
    status: TaskStatus = Field(alias="type")
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    exit_code: Optional[int] = None
    signal: Optional[str] = None
    log_path: Optional[str] = None
    log_url: Optional[str] = None
    stdout_lines: Optional[int] = None
    stderr_lines: Optional[int] = None
    artifact_urls: list[str] = []
    resource_usage: Optional[dict[str, Any]] = None
    retry_count: int = 0
    error: Optional[dict[str, Any]] = None
    reason: Optional[str] = None

    class Config:
        populate_by_name = True


class Summary(BaseModel):
    """Summary of task execution."""

    total_steps: int
    successful_steps: int
    failed_steps: int
    skipped_steps: int
    crashed_steps: int
    total_duration_seconds: float
    total_artifacts: int
    total_log_lines: int


class ExecutionResult(BaseModel):
    """Complete task execution result."""

    schema_version: str = "1.0.0"
    task_id: str
    status: TaskStatus = Field(alias="type")
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: float
    device_info: dict[str, Any]
    steps: list[StepResult]
    summary: Summary
    ai_rca: Optional[dict[str, Any]] = None
    forensics: dict[str, Any] = {}

    class Config:
        populate_by_name = True


class Heartbeat(BaseModel):
    """Runner heartbeat data."""

    device_id: str
    runner_version: str
    status: RunnerStatus = Field(alias="type")
    current_task_id: Optional[str] = None
    current_task_progress: float = 0.0
    system_resources: dict[str, Any]
    capabilities: dict[str, Any]
    last_report: str

    class Config:
        populate_by_name = True


# Database Models (SQLAlchemy)


from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TaskQueueDB(Base):
    """Database model for queued tasks."""

    __tablename__ = "task_queue"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, index=True, nullable=False, default="pending")
    priority = Column(String, default="normal")
    device_binding = Column(JSON, nullable=False)
    task_manifest = Column(JSON, nullable=False)
    assigned_device_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    result = Column(JSON, nullable=True)


class DeviceHeartbeatDB(Base):
    """Database model for device heartbeats."""

    __tablename__ = "device_heartbeats"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, nullable=False)
    current_task_id = Column(String, nullable=True)
    current_task_progress = Column(Float, default=0.0)
    system_resources = Column(JSON, nullable=False)
    capabilities = Column(JSON, nullable=False)
    runner_version = Column(String, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, index=True)


class TaskDependencyDB(Base):
    """Database model for task dependencies."""

    __tablename__ = "task_dependencies"

    id = Column(Integer, primary_key=True, index=True)
    task_id_one = Column(Integer, ForeignKey("task_queue.id"), index=True, nullable=False)
    task_id_two = Column(Integer, ForeignKey("task_queue.id"), index=True, nullable=False)
    dependency_type = Column(String, nullable=False)  # 'after_complete', 'after_start'
    status = Column(String, default="active", nullable=False)  # 'active', 'resolved', 'skipped'
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)


class DeviceLockDB(Base):
    """Database model for device resource locks."""

    __tablename__ = "device_locks"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    task_id = Column(Integer, ForeignKey("task_queue.id"), index=True, nullable=False)
    status = Column(String, default="locked", nullable=False)  # 'locked', 'acquired', 'released'
    lock_timeout_seconds = Column(Integer, default=300, nullable=False)
    acquired_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    released_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ============================================
# User and Authentication Models
# ============================================


class UserDB(Base):
    """Database model for users."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    github_id = Column(String, unique=True, index=True, nullable=True)
    gitlab_id = Column(String, unique=True, index=True, nullable=True)
    avatar_url = Column(String, nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RoleDB(Base):
    """Database model for user roles."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PermissionDB(Base):
    """Database model for permissions."""

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    resource_type = Column(String, index=True, nullable=False)  # device, task, application, setting
    action = Column(String, nullable=True)  # create, read, update, delete
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSettingsDB(Base):
    """Database model for user preferences."""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    preferences = Column(JSON, nullable=False)
    theme = Column(String, default="light")
    language = Column(String, default="en")
    notification_email = Column(Boolean, default=True)
    notification_web = Column(Boolean, default=True)
    timezone = Column(String, default="UTC")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationDB(Base):
    """Database model for user notifications."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    type = Column(String, index=True, nullable=False)  # info, success, warning, error
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False, index=True)
    link_url = Column(String, nullable=True)
    meta_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AuditLogDB(Base):
    """Database model for audit logging."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, index=True, nullable=False)
    entity_id = Column(String, index=True, nullable=True)
    details = Column(JSON, nullable=False)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ============================================
# Test Management Models
# ============================================


class TestApplicationDB(Base):
    """Database model for test applications (SUTs)."""

    __tablename__ = "test_applications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, index=True, nullable=False)  # web, mobile, hardware, api, iot
    version = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppEnvironmentDB(Base):
    """Database model for application environments."""

    __tablename__ = "app_environments"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("test_applications.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, index=True, nullable=False)  # development, testing, staging, production
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================
# System Configuration Models
# ============================================


class SystemSettingDB(Base):
    """Database model for global system settings."""

    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    category = Column(
        String, index=True, nullable=False
    )  # general, auth, notification, api, service
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)  # whether frontend can read
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ServiceHealthDB(Base):
    """Database model for service health monitoring."""

    __tablename__ = "service_health"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, index=True, nullable=False)  # healthy, unhealthy, degraded
    last_check = Column(DateTime, default=datetime.utcnow, index=True)
    uptime_seconds = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
