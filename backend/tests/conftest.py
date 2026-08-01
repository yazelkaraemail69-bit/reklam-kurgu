"""Pytest fixtures."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import create_app


@pytest.fixture
def temp_db():
    """Geçici SQLite database."""
    db_path = tempfile.mktemp(suffix=".db")
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def app():
    """Test FastAPI uygulaması."""
    return create_app()


@pytest.fixture
def client(app):
    """Test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)
