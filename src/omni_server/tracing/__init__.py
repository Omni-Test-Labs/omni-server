"""Tracing and observability setup for omni-server."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

import structlog


class TelemetrySetup:
    """Setup distributed tracing and structured logging."""

    def __init__(self, service_name: str = "omni-server", debug: bool = False):
        self.service_name = service_name
        self.debug = debug
        self.tracer = None

    def setup_jaeger(self, host: str = "localhost", port: int = 6831, enabled: bool = False):
        """Initialize Jaeger exporter for distributed tracing."""
        tracer_provider = TracerProvider()
        tracer_provider.resource = {"service.name": self.service_name}

        if enabled:
            try:
                from opentelemetry.exporter.jaeger import JaegerExporter

                jaeger_exporter = JaegerExporter(
                    agent_host_name=host,
                    agent_port=port,
                    max_tag_value_length=4096,
                )

                span_processor = BatchSpanProcessor(jaeger_exporter)
                tracer_provider.add_span_processor(span_processor)
            except ImportError:
                if self.debug:
                    structlog.get_logger().warning(
                        "Jaeger exporter not available, using console exporter"
                    )
                console_exporter = ConsoleSpanExporter()
                tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
        else:
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

        trace.set_tracer_provider(tracer_provider)
        self.tracer = trace.get_tracer(__name__)

        if self.debug:
            structlog.get_logger().info(
                "Distributed tracing initialized",
                service=self.service_name,
                jaeger_enabled=enabled,
                jaeger_host=host,
                jaeger_port=port,
            )

    def setup_structlog(self):
        """Initialize structured logging."""
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        if self.debug:
            structlog.get_logger().info("Structured logging initialized")

    def instrument_fastapi(self, app):
        """Instrument FastAPI application for tracing."""
        FastAPIInstrumentor.instrument_app(app)
        if self.debug:
            structlog.get_logger().info("FastAPI tracing instrumentation enabled")

    def instrument_sqlalchemy(self, engine):
        """Instrument SQLAlchemy for tracing."""
        SQLAlchemyInstrumentor().instrument(engine=engine)
        if self.debug:
            structlog.get_logger().info("SQLAlchemy tracing instrumentation enabled")


def get_logger(**kwargs):
    """Get structured logger with optional context."""
    from opentelemetry import trace

    logger = structlog.get_logger()

    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()

    if span_context.is_valid:
        trace_id = span_context.trace_id
        span_id = span_context.span_id
        return logger.bind(
            service="omni-server",
            trace_id=f"{trace_id:032x}",
            span_id=f"{span_id:016x}",
            **kwargs,
        )

    return logger.bind(service="omni-server", **kwargs)


__all__ = ["TelemetrySetup", "get_logger"]
