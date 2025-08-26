
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from sqlaudit._internals.registry import audit_model_registry


@pytest.fixture(scope="function")
def db_session():
    """
    Fixture that provides a fresh in-memory database and DeclarativeBase for each test.
    Returns a tuple of (SessionLocal, Base).
    """
    class Base(DeclarativeBase): ...

    url = "sqlite:///:memory:"
    engine = create_engine(url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield SessionLocal, Base
    audit_model_registry.clear()
   
   
def get_db(db_session):
    """Helper function to get a database session."""
    SessionLocal, _ = db_session
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

