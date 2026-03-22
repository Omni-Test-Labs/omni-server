"""RCA prompt builder for constructing LLM prompts with appropriate context."""

from datetime import datetime
from typing import Any

from omni_server.ai.llm_client import LLMConfig


class RCAContext:
    """Structured context for RCA analysis."""

    def __init__(
        self,
        task_id: str,
        task_name: str,
        task_description: str,
        task_type: str,
        task_params: dict[str, Any],
        device_id: str | None = None,
        device_hostname: str | None = None,
        device_ip: str | None = None,
        device_status: str | None = None,
        status: str = "unknown",
        started_at: str | None = None,
        completed_at: str | None = None,
        error_message: str | None = None,
        retry_count: int = 0,
        max_retries: int = 3,
        total_steps: int = 0,
        completed_steps: int = 0,
        failed_steps: list[tuple[int, str, str]] | None = None,
        logs: list[dict[str, Any]] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
    ):
        self.task_id = task_id
        self.task_name = task_name
        self.task_description = task_description
        self.task_type = task_type
        self.task_params = task_params
        self.device_id = device_id
        self.device_hostname = device_hostname
        self.device_ip = device_ip
        self.device_status = device_status
        self.status = status
        self.started_at = started_at
        self.completed_at = completed_at
        self.error_message = error_message
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.total_steps = total_steps
        self.completed_steps = completed_steps
        self.failed_steps = failed_steps or []
        self.logs = logs or []
        self.artifacts = artifacts or []

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for JSON serialization."""
        return {
            "task": {
                "id": self.task_id,
                "name": self.task_name,
                "description": self.task_description,
                "type": self.task_type,
                "params": self.task_params,
                "status": self.status,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "error_message": self.error_message,
                "retry_count": self.retry_count,
                "max_retries": self.max_retries,
            },
            "device": {
                "id": self.device_id,
                "hostname": self.device_hostname,
                "ip_address": self.device_ip,
                "status": self.device_status,
            }
            if self.device_id
            else None,
            "execution": {
                "total_steps": self.total_steps,
                "completed_steps": self.completed_steps,
                "failed_steps": [
                    {
                        "step_number": step_no,
                        "step_name": name,
                        "error": error,
                    }
                    for step_no, name, error in self.failed_steps
                ],
            },
            "artifacts": {
                "logs": self.logs[:20],  # Limit to first 20 logs
                "files": [
                    {
                        "path": artifact.get("path"),
                        "size": artifact.get("size"),
                    }
                    for artifact in self.artifacts
                ],
            },
        }


class RCAPromptBuilder:
    """Builds prompts for RCA analysis with task context."""

    # Base system prompt defining the AI's role and guidelines
    SYSTEM_PROMPT = """You are an expert system for diagnosing task failures in automated testing infrastructure.

Your role is to analyze failed task executions and provide actionable root cause analysis. Focus on:
1. Identifying the actual root cause (not just symptoms)
2. Providing clear, actionable recommendations
3. Assessing severity and priority
4. Distinguishing between infrastructure issues, test issues, and configuration problems

Analysis Guidelines:
- Always consider the full execution context (device state, steps taken, errors encountered)
- Look for patterns across multiple failed steps
- Check for common infrastructure issues (network, resource contention, timeouts)
- Verify if parameters or configurations might cause failures
- Consider retry behavior and timing patterns

Output Format:
Provide analysis in JSON format with these fields:
- root_cause: Brief statement of the primary issue
- confidence: float (0.0-1.0) indicating confidence level
- severity: one of "critical", "high", "medium", "low"
- findings: array of strings describing key observations
- recommendations: array of actionable steps to fix or prevent"""

    def __init__(self):
        """Initialize the prompt builder."""
        pass

    def build_prompt(
        self,
        context: RCAContext,
        include_debugging: bool = False,
    ) -> tuple[str, str]:
        """
        Build prompt for RCA analysis.

        Args:
            context: The RCA context containing task, device, and execution info
            include_debugging: Whether to include debugging hints

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = self._get_system_prompt(include_debugging)
        user_prompt = self._build_user_prompt(context)

        return system_prompt, user_prompt

    def build_config(self, include_debugging: bool = False, max_tokens: int = 4000) -> LLMConfig:
        """
        Build LLM configuration for RCA analysis.

        Args:
            include_debugging: Whether to include debugging hints
            max_tokens: Maximum tokens in response

        Returns:
            LLMConfig instance
        """
        return LLMConfig(
            provider="openai",  # Default provider
            model="gpt-4o-mini",  # Default model
            api_key="test-api-key",  # Should be provided by config in production
            temperature=0.3,  # Low temperature for consistent analysis
            max_tokens=max_tokens,
            top_p=0.9,
        )

    def _get_system_prompt(self, include_debugging: bool) -> str:
        """Get the system prompt for RCA analysis."""
        if include_debugging:
            return f"""{self.SYSTEM_PROMPT}

Debugging Mode:
Provide additional technical details about:
- Specific error codes and their meanings
- Potential interdependencies between components
- Diagnostic commands or queries to run
- Expected vs actual state comparisons"""
        return self.SYSTEM_PROMPT

    def _build_user_prompt(self, context: RCAContext) -> str:
        """Build the user prompt with task context."""
        context_dict = context.to_dict()

        prompt_parts = [
            "# Task Failure Analysis Request",
            "",
            "Please analyze the following failed task execution and provide root cause analysis.",
            "",
            "## Task Information",
            f"Task ID: {context_dict['task']['id']}",
            f"Name: {context_dict['task']['name']}",
            f"Type: {context_dict['task']['type']}",
            f"Description: {context_dict['task']['description'] or 'N/A'}",
            f"Parameters: {_format_dict(context_dict['task']['params'])}",
            f"Status: {context_dict['task']['status']}",
            f"Started: {context_dict['task']['started_at'] or 'N/A'}",
            f"Completed: {context_dict['task']['completed_at'] or 'N/A'}",
            f"Retry Count: {context_dict['task']['retry_count']}/{context_dict['task']['max_retries']}",
        ]

        if context_dict["task"].get("error_message"):
            prompt_parts.extend(
                [
                    "",
                    "## Error Message",
                    context_dict["task"]["error_message"],
                ]
            )

        if context_dict["device"]:
            device = context_dict["device"]
            prompt_parts.extend(
                [
                    "",
                    "## Device Information",
                    f"Device ID: {device['id']}",
                    f"Hostname: {device['hostname'] or 'N/A'}",
                    f"IP Address: {device['ip'] or 'N/A'}",
                    f"Device Status: {device['status'] or 'N/A'}",
                ]
            )

        execution = context_dict["execution"]
        prompt_parts.extend(
            [
                "",
                "## Execution Summary",
                f"Total Steps: {execution['total_steps']}",
                f"Completed Steps: {execution['completed_steps']}",
                f"Failed Steps: {len(execution['failed_steps'])}",
            ]
        )

        if execution["failed_steps"]:
            prompt_parts.append("")
            prompt_parts.append("### Failed Steps Details")
            for idx, step in enumerate(execution["failed_steps"], 1):
                prompt_parts.extend(
                    [
                        f"**Step {idx}** (#{step['step_number']}: {step['step_name']})",
                        f"Error: {step['error']}",
                    ]
                )

        artifacts = context_dict["artifacts"]
        if artifacts["logs"]:
            prompt_parts.append("")
            prompt_parts.append(
                f"## Recent Logs (showing {len(artifacts['logs'])} of potentially more)"
            )
            for log in artifacts["logs"]:
                timestamp = log.get("timestamp", "N/A")
                level = log.get("level", "INFO")
                message = log.get("message", "")
                prompt_parts.append(f"[{timestamp}] {level}: {message}")

        if artifacts["files"]:
            prompt_parts.append("")
            prompt_parts.append("## Artifacts")
            for file in artifacts["files"]:
                prompt_parts.append(f"- {file['path']} ({file.get('size', 'N/A')} bytes)")

        prompt_parts.extend(
            [
                "",
                "## Analysis Request",
                "Based on the information above, please provide:",
                "1. Root cause of the failure",
                "2. Confidence level in your analysis (0.0-1.0)",
                "3. Severity assessment (critical/high/medium/low)",
                "4. Key findings from the logs and execution",
                "5. Actionable recommendations to fix or prevent this issue",
                "",
                "Respond with a JSON object in the following format:",
                """{
    "root_cause": "Brief description of the primary issue",
    "confidence": 0.85,
    "severity": "high",
    "findings": [
        "Observation 1",
        "Observation 2"
    ],
    "recommendations": [
        "Actionable step 1",
        "Actionable step 2"
    ]
}""",
                "",
                f"Analysis generated at: {datetime.utcnow().isoformat()}Z",
            ]
        )

        return "\n".join(prompt_parts)


def _format_dict(d: dict[str, Any] | None, indent: int = 0) -> str:
    """Format a dictionary for display in the prompt."""
    if not d:
        return "N/A"

    lines = []
    prefix = "  " * indent

    for key, value in d.items():
        value_str = str(value)
        if isinstance(value, dict):
            nested = _format_dict(value, indent + 1)
            lines.append(f"{prefix}{key}:")
            for nested_line in nested.split("\n"):
                lines.append(f"  {nested_line}")
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}: [{', '.join(map(str, value))}]")
        else:
            lines.append(f"{prefix}{key}: {value_str}")

    return "\n".join(lines)
