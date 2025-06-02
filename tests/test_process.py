import datetime
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlaudit.process import _audit_changes_values_encoder


@pytest.fixture(scope="function")
def SessionLocal():
    """Fixture to create a new SQLAlchemy session for each test."""

    # engine = create_engine("sqlite:///:memory:")
    engine = create_engine("sqlite:///test_database.db")  # File-based SQLite database
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield SessionLocal


def get_db(SessionLocal):
    """Helper function to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_audit_change_encoder():
    changes = [
        uuid.uuid4(),
        datetime.datetime.now(),
        "test_string",
        123,
        [1, 2, 3],
        {"key": "value"},
    ]

    encoded_changes = _audit_changes_values_encoder(changes)

    assert isinstance(encoded_changes, list), "Encoded changes should be a list."
    assert all(isinstance(change, str) for change in encoded_changes), (
        "All encoded changes should be strings."
    )

    
