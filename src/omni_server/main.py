"""FastAPI application main entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from omni_server.database import init_db
from omni_server.config import Settings

from omni_server.api.v1 import router as v1_router
from omni_server.api.v2 import router as v2_router
from omni_server.api.v3 import router as v3_router
from omni_server.middleware.versioning import VersionNegotiationMiddleware
from omni_server.auth.routes import router as auth_router
from omni_server.admin.users.routes import router as users_router, audit_router

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and event bus on startup."""
    from omni_server.events import get_event_bus
    from omni_server.tracing import TelemetrySetup
    from omni_server.queue import init_rca_config, _config_cache as queue_config_cache
    from omni_server.database import engine

    init_db()

    init_rca_config(settings)

    telemetry = TelemetrySetup(
        service_name="omni-server",
        debug=settings.debug,
    )

    jaeger_enabled = settings.debug
    telemetry.setup_jaeger(enabled=jaeger_enabled)
    telemetry.setup_structlog()
    telemetry.instrument_sqlalchemy(engine)

    event_bus = get_event_bus()
    await event_bus.start()

    yield

    await event_bus.stop()


app = FastAPI(
    title="Omni-Server API",
    description="Central task queue and device management for Omni-Test-Labs",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(VersionNegotiationMiddleware)

app.include_router(v1_router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api/v2")
app.include_router(v3_router, prefix="/api/v3")
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(audit_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Omni-Server: Central control server for Omni-Test-Labs",
        "docs": "/docs",
        "redoc": "/redoc",
    }
