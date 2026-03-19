"""Test configuration and shared fixtures."""

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import omni_server.database as db_module
from omni_server.database import get_db
from omni_server.main import app
from omni_server.models import Base

# Store original engine to restore after tests
orig_engine = db_module.engine
orig_SessionLocal = db_module.SessionLocal

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}, echo=False
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def setup_test_db():
    """Setup test database for the application."""
    # Replace the application database with test database
    db_module.engine = test_engine
    db_module.SessionLocal = TestingSessionLocal


def teardown_test_db():
    """Restore original database configuration."""
    db_module.engine = orig_engine
    db_module.SessionLocal = orig_SessionLocal


@pytest.fixture(scope="function", autouse=True)
def test_db_setup():
    """Setup and teardown test database for all tests."""
    setup_test_db()
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    teardown_test_db()


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    session = TestingSessionLocal()
    try:
        yield session
        # Only commit if the transaction is still active
        try:
            session.commit()
        except Exception:
            # If commit fails (e.g., due to rollback), just ignore
            pass
    finally:
        try:
            session.rollback()
        except Exception:
            pass
        session.close()


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override."""

    def override_get_db() -> Generator[Session, None, None]:
        """Override to use the test database session."""
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as api_client:
            yield api_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override.

    This ensures the database tables are created before the client is used,
    and the client uses the same database session as the db fixture.
    """
    # Create database tables for the test client
    Base.metadata.create_all(bind=test_engine)

    def override_get_db() -> Generator[Session, None, None]:
        """Override to use the test database session."""
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def sample_task_manifest():
    """Sample task manifest for testing."""
    return {
        "schema_version": "1.0.0",
        "task_id": "test-task-001",
        "created_at": "2024-03-18T10:00:00Z",
        "device_binding": {"device_id": "device-001", "device_type": "pc", "oob_methods": []},
        "priority": "normal",
        "timeout_seconds": 300,
        "pipeline": [
            {
                "step_id": "step-1",
                "order": 1,
                "type": "shell",
                "cmd": "echo hello",
                "working_dir": None,
                "must_pass": True,
                "depends_on": [],
                "always_run": False,
                "timeout_seconds": 10,
            }
        ],
    }


@pytest.fixture
def sample_heartbeat():
    """Sample heartbeat data for testing."""
    return {
        "device_id": "device-001",
        "runner_version": "0.1.0",
        "type": "idle",
        "current_task_id": None,
        "current_task_progress": 0.0,
        "system_resources": {"cpu_percent": 10.0, "memory_mb": 8192},
        "capabilities": {"python": "3.10", "os": "linux"},
        "last_report": "2024-03-18T10:00:00Z",
    }
