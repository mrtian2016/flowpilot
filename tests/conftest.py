
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from flowpilot.core import db
from flowpilot.core.db import Base, SessionLocal

@pytest.fixture(name="session")
def session_fixture():
    """Create a new database session for a test."""
    # Create in-memory SQLite engine
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Override global engine in db module if needed, or just bind Base
    # Note: flowpilot code uses db.get_engine(). We might need to mock or set it.
    # flowpilot.core.db provides set_engine() for this purpose!
    
    db.set_engine(engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    try:
        with SessionLocal() as session:
            yield session
    finally:
        db.reset_engine()
