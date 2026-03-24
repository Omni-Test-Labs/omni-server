"""Tracing decorators for automatic span instrumentation."""

import functools
from typing import Callable, ParamSpec, TypeVar

from opentelemetry import trace

P = ParamSpec("P")
R = TypeVar("R")


def traced(operation_name: str | None = None):
    """Decorator to trace function execution."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        name = operation_name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            tracer = trace.get_tracer(__name__)

            with tracer.start_as_current_span(name) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = func(*args, **kwargs)
                    span.set_status("OK")
                    return result
                except Exception as e:
                    span.set_status("ERROR", str(e))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise

        return wrapper

    return decorator


def async_traced(operation_name: str | None = None):
    """Decorator to trace async function execution."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        name = operation_name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            tracer = trace.get_tracer(__name__)

            with tracer.start_as_current_span(name) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = await func(*args, **kwargs)
                    span.set_status("OK")
                    return result
                except Exception as e:
                    span.set_status("ERROR", str(e))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise

        return async_wrapper

    return decorator


__all__ = ["traced", "async_traced"]
