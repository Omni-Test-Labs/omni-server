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

# Import all models to ensure they're registered with SQLAlchemy's metadata
import omni_server.models

# Store original engine to restore after tests
orig_engine = db_module.engine
orig_SessionLocal = db_module.SessionLocal

# Use file-based SQLite for testing (more reliable than in-memory for shared access)
import tempfile
import os

temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
temp_db_file.close()
TEST_DATABASE_URL = f"sqlite:///{temp_db_file.name}"

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
    # Tables are now created in the client fixture to ensure they exist before use
    yield
    teardown_test_db()


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    # Create tables first before creating the session
    Base.metadata.create_all(bind=test_engine)

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


@pytest.fixture(scope="function", autouse=True)
def seed_default_roles(db: Session):
    """Seed default roles into the database for tests."""
    from omni_server.models import RoleDB

    # Check if roles already exist
    existing_roles = db.query(RoleDB).all()
    if len(existing_roles) == 0:
        # Create default roles only if they don't exist
        roles = [
            RoleDB(
                name="admin",
                description="Administrator with full access",
                permissions=["*"],
            ),
            RoleDB(
                name="user",
                description="Regular user with limited access",
                permissions=["read", "create"],
            ),
        ]

        for role in roles:
            db.add(role)
        db.commit()

    yield


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override.

    This ensures the database tables are created before the client is used,
    and the client uses the same database session as the db fixture.
    """
    # Tables are already created in the db fixture

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
def auth_headers(client):
    """Create and return authentication headers for a test user.

    This fixture registers a new user, logs them in, and returns
    the auth headers that can be used for authenticated API calls.
    """
    # Register a user
    user_data = {
        "username": "authuser",
        "email": "authuser@example.com",
        "password": "AuthPass123",
    }
    client.post("/api/auth/register", json=user_data)

    # Login to get tokens
    login_response = client.post(
        "/api/auth/login", json={"identifier": "authuser", "password": "AuthPass123"}
    )
    access_token = login_response.json()["access_token"]

    # Return headers
    return {"Authorization": f"Bearer {access_token}"}


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
