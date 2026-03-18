"""Database initialization and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from omni_server.config import Settings
from omni_server.models import Base

settings = Settings()

engine = create_engine(settings.database_url, echo=settings.debug)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
