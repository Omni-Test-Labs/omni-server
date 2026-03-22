"""RCA context extraction and preparation service."""

from datetime import datetime
from typing import Any, Optional
from sqlalchemy.orm import Session

from omni_server.models import TaskQueueDB, DeviceHeartbeatDB
from loguru import logger


class RCAContextExtractor:
    """Extracts and prepares context for Root Cause Analysis."""

    def __init__(self):
        """Initialize the extractor."""

    def extract_context_from_task(self, db: Session, task_id: str) -> dict[str, Any]:
        """
        Extract complete RCA context from task and related data.

        Args:
            db: Database session
            task_id: Task ID to analyze

        Returns:
            Dictionary containing:
            - task: Task information
            - device: Device context
            - execution: Execution results and steps
            - artifacts: Error logs and data files
        """
        # Get task from database
        task = db.query(TaskQueueDB).filter(TaskQueueDB.task_id == task_id).first()
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Get device information if task is assigned
        device = None
        if task.assigned_device_id:
            device = (
                db.query(DeviceHeartbeatDB)
                .filter(DeviceHeartbeatDB.device_id == task.assigned_device_id)
                .first()
            )

        # Build context
        context = {
            "task": self._extract_task_info(task),
            "device": self._extract_device_info(device) if device else None,
            "execution": self._extract_execution_results(task),
            "artifacts": self._extract_artifacts(task),
        }

        logger.info(f"Extracted RCA context for task {task_id}")

        return context

    def _extract_task_info(self, task: TaskQueueDB) -> dict[str, Any]:
        """Extract task information."""
        return {
            "task_id": task.task_id,
            "status": task.status,
            "priority": task.priority,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": None,
            "duration_seconds": 0.0,
            "manifest": task.task_manifest if hasattr(task, "task_manifest") else {},
        }

    def _extract_device_info(self, device: DeviceHeartbeatDB) -> dict[str, Any]:
        """Extract device context."""
        return {
            "device_id": device.device_id,
            "status": device.status,
            "runner_version": device.runner_version,
            "hostname": "unknown",  # Not stored in DeviceHeartbeatDB
            "os": "unknown",  # Not stored in DeviceHeartbeatDB
            "capabilities": device.capabilities if hasattr(device, "capabilities") else {},
        }

    def _extract_execution_results(self, task: TaskQueueDB) -> dict[str, Any]:
        """Extract execution results and step-by-step details."""
        result = task.result if task.result else {}

        # Extract summary
        summary = result.get("summary", {})
        execution = {
            "summary": {
                "total_steps": summary.get("total_steps", 0),
                "successful_steps": summary.get("successful_steps", 0),
                "failed_steps": summary.get("failed_steps", 0),
                "crashed_steps": summary.get("crashed_steps", 0),
                "skipped_steps": summary.get("skipped_steps", 0),
                "total_duration_seconds": summary.get("total_duration_seconds", 0.0),
                "total_artifacts": summary.get("total_artifacts", 0),
                "total_log_lines": summary.get("total_log_lines", 0),
            }
        }

        # Extract step-by-step execution details
        steps = result.get("steps", [])
        execution["steps"] = self._extract_step_details(steps)

        # Add timestamp info if available
        if result.get("started_at"):
            try:
                execution["started_at"] = result["started_at"]
            except Exception:
                execution["started_at"] = None

        if result.get("completed_at"):
            try:
                execution["completed_at"] = result["completed_at"]
                execution["duration_seconds"] = result.get("duration_seconds", 0.0)
            except Exception:
                execution["completed_at"] = None
                execution["duration_seconds"] = 0.0
        elif execution["summary"]["total_duration_seconds"] > 0:
            execution["duration_seconds"] = execution["summary"]["total_duration_seconds"]

        return execution

    def _extract_step_details(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract step-by-step execution details."""
        step_details = []

        for step in steps:
            step_info = {
                "step_id": step.get("step_id", "unknown"),
                "type": step.get("type", "unknown"),
                "status": step.get("status", "unknown"),
                "exit_code": step.get("exit_code"),
                "stdout": step.get("stdout", ""),
                "stderr": step.get("stderr", ""),
                "started_at": step.get("started_at"),
                "completed_at": step.get("completed_at"),
                "duration_seconds": step.get("duration_seconds", 0.0),
            }

            # Extract error message
            if step.get("error_message"):
                step_info["error_message"] = step["error_message"]

            step_details.append(step_info)

        return step_details

    def _extract_artifacts(self, task: TaskQueueDB) -> dict[str, Any]:
        """Extract error logs and artifacts from task result."""
        result = task.result if task.result else {}

        # Extract logs
        logs = []
        if result.get("logs"):
            logs.extend(result["logs"])

        # Extract file artifacts
        files = []
        if result.get("artifacts"):
            for artifact in result.get("artifacts", []):
                files.append(
                    {
                        "name": artifact.get("name", "unknown"),
                        "type": artifact.get("type", "unknown"),
                        "size": artifact.get("size", 0),
                        "location": artifact.get("location", ""),
                    }
                )

        return {
            "logs": logs,
            "files": files,
        }
