"""FastAPI application main entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from omni_server.database import init_db
from omni_server.config import Settings

from omni_server.api import tasks, devices, dependencies
from omni_server.auth.routes import router as auth_router
from omni_server.admin.users.routes import router as users_router, audit_router

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()

    from omni_server.queue import init_rca_config, _config_cache as queue_config_cache

    init_rca_config(settings)

    yield


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

app.include_router(tasks.router)
app.include_router(dependencies.router)
app.include_router(devices.router)
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
