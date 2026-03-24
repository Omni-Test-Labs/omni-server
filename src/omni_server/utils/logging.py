"""Structured logging utilities for omni-server."""

from typing import Any

from opentelemetry import trace

from omni_server.tracing import get_logger


class TaskLogger:
    """Logger for task-related operations with automatic context."""

    def __init__(self, task_id: str, **kwargs):
        self.task_id = task_id
        self.base_context = {"task_id": task_id, **kwargs}

    def get_context(self, **kwargs):
        """Get logger with all context applied."""
        context = {**self.base_context, **kwargs}

        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()

        if span_context.is_valid:
            trace_id = span_context.trace_id
            span_id = span_context.span_id
            context.update(
                trace_id=f"{trace_id:032x}",
                span_id=f"{span_id:016x}",
            )

        return context

    def info(self, message: str, **kwargs):
        """Log info message."""
        context = self.get_context(**kwargs)
        get_logger(**context).info(message)

    def error(self, message: str, **kwargs):
        """Log error message."""
        context = self.get_context(**kwargs)
        get_logger(**context).error(message)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        context = self.get_context(**kwargs)
        get_logger(**context).warning(message)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        context = self.get_context(**kwargs)
        get_logger(**context).debug(message)


class DeviceLogger:
    """Logger for device-related operations with automatic context."""

    def __init__(self, device_id: str, **kwargs):
        self.device_id = device_id
        self.base_context = {"device_id": device_id, **kwargs}

    def get_context(self, **kwargs):
        """Get logger with all context applied."""
        context = {**self.base_context, **kwargs}

        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()

        if span_context.is_valid:
            trace_id = span_context.trace_id
            span_id = span_context.span_id
            context.update(
                trace_id=f"{trace_id:032x}",
                span_id=f"{span_id:016x}",
            )

        return context

    def info(self, message: str, **kwargs):
        """Log info message."""
        context = self.get_context(**kwargs)
        get_logger(**context).info(message)

    def error(self, message: str, **kwargs):
        """Log error message."""
        context = self.get_context(**kwargs)
        get_logger(**context).error(message)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        context = self.get_context(**kwargs)
        get_logger(**context).warning(message)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        context = self.get_context(**kwargs)
        get_logger(**context).debug(message)


def log_exception(logger, exc: Exception, context: dict[str, Any] | None = None):
    """Log exception with context."""
    ctx = context or {}
    logger.bind(
        error_type=type(exc).__name__,
        error_message=str(exc),
        **ctx,
    ).error("Exception occurred", exc_info=exc)


__all__ = ["TaskLogger", "DeviceLogger", "log_exception"]
