import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlaudit.retrieval import (
    _ensure_valid_resource_ids,
)


@pytest.fixture(scope="function")
def SessionLocal():
    """Fixture to create a new SQLAlchemy session for each test."""
    
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield SessionLocal


def get_db(SessionLocal):
    """Helper function to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def test_ensure_valid_resource_ids(SessionLocal: sessionmaker):
    """
    Test the retrieval of resource changes with valid resource IDs.
    This test checks if the get_resource_changes function correctly retrieves changes for valid resource IDs.
    """
    unique_id = uuid.uuid4()
    ids = _ensure_valid_resource_ids([1, "2", unique_id]) 
    assert len(ids) == 3, f"Expected all valid resource IDs in list, got {ids}"

    ids = _ensure_valid_resource_ids("1")
    assert len(ids) == 1 and ids[0] == "1", "Expected single valid resource ID in list"
    
    
    ids = _ensure_valid_resource_ids(None) # Is valid as it will be ignored in the retrieval function
    assert len(ids) == 0, "Expected empty list for None input"

def test_ensure_invalid_resource_ids(SessionLocal: sessionmaker):
    """
    Test the retrieval of resource changes with invalid resource IDs.
    This test checks if the get_resource_changes function raises an error for invalid resource IDs.
    """
    with pytest.raises(TypeError):
        _ensure_valid_resource_ids(["valid", 2.5, None]) # type: ignore

    with pytest.raises(TypeError):
        _ensure_valid_resource_ids(2.5)  # type: ignore

    
