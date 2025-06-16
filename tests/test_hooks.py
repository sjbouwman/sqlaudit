import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from sqlaudit._internals.types import LogContextInternal
from sqlaudit.hooks import _audit_change_buffer
from sqlaudit._internals.types import AuditChange
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

def test_audit_change_buffer(db_session):
    """
    Test the AuditChangeBuffer functionality.
    This test checks if the buffer correctly collects and clears audit changes.
    """
    SessionLocal, Base = db_session

    # We first check that the buffer is empty
    assert len(_audit_change_buffer.items()) == 0, (
        "Audit change buffer should be empty initially."
    )
    # We add some dummy changes to the buffer

    changes = [
        AuditChange(field="name", old_value="old_name", new_value="new_name"),
        AuditChange(field="email", old_value="old_email", new_value="new_email"),
    ]

    class DummyModel(Base):
        __tablename__ = "dummy_model"
        id: Mapped[int] = mapped_column(primary_key=True)

    dummy_instance = DummyModel(id=1)
    context = LogContextInternal(timestamp=datetime.datetime.now(datetime.UTC))

    assert dummy_instance not in _audit_change_buffer and len(_audit_change_buffer) == 0, (
        "Dummy instance should not be in the buffer before adding changes."
    )

    # Simulate adding changes to the buffer
    _audit_change_buffer.add(dummy_instance, changes, context=context)
    
    assert dummy_instance in _audit_change_buffer, (
        "Dummy instance should be in the buffer after adding changes."
    )


    for classtype, _ in _audit_change_buffer.items():
        assert classtype == dummy_instance.__class__, "Buffered instance should match the dummy instances class."

