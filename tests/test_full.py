import datetime
import uuid

import pytest
from sqlalchemy import UUID, ForeignKey, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)
from tzlocal import get_localzone

from sqlaudit._internals.registry import audit_model_registry
from sqlaudit._internals.utils import get_user_id_from_instance
from sqlaudit.config import (
    SQLAuditConfig,
    clear_config,
    set_config,
)
from sqlaudit.decorators import track_table
from sqlaudit.hooks import register_hooks
from sqlaudit.retrieval import get_resource_changes
from sqlaudit.types import SQLAuditChange, SQLAuditRecord
from tests.utils.db import create_user_model


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


def test_full_audit_flow(db_session):
    """
    Test the full audit flow including configuration, buffer management, and change registration.
    This test checks if the audit system correctly collects and processes changes.
    """
    SessionLocal, Base = db_session

    # Clear any existing configuration
    clear_config()

    User = create_user_model(Base)

    test_user = User(
        user_id=1,
        first_name="John",
        last_name="Doe",
        email="jdoe@example.com",
    )

    # We create a model instance to test with

    @track_table(
        tracked_fields=[
            "name",
            "email",
            "created_by_user_id",
            "barcode",
            "created_at",
            "rating",
        ],
        user_id_field="created_by_user_id",
    )
    class Customer(Base):
        __tablename__ = "customer"
        id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
        name: Mapped[str] = mapped_column()
        email: Mapped[str] = mapped_column()
        created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
        created_at: Mapped[datetime.datetime] = mapped_column(
            default=datetime.datetime.now
        )

        barcode: Mapped[uuid.UUID] = mapped_column(
            UUID(as_uuid=True), unique=True, default=uuid.uuid4
        )

        rating: Mapped[float] = mapped_column(default=0.5)

    config = SQLAuditConfig(
        session_factory=lambda: get_db(db_session),
        user_model=User,
        user_model_user_id_field="user_id",
        get_user_id_callback=lambda: get_user_id_from_instance(test_user, "user_id"),
    )

    set_config(config)

    # We have to register the hooks
    register_hooks()

    with next(get_db(db_session)) as session:
        session: Session
        # Create the tables
        Base.metadata.create_all(bind=session.get_bind())

        # Add the test user to the session
        session.add(test_user)
        session.commit()

        # Create a customer instance
        customer = Customer(
            name="Jane Doe",
            email="janedoe@example.com",
            created_by_user_id=test_user.user_id,
        )

        # Add the customer to the session
        session.add(customer)

        # Add the second customer to the session
        session.commit()

        session.refresh(customer)

        # At this point, the audit change buffer should have collected changes
        tz = get_localzone()
        audit_records = get_resource_changes(
            Customer,
            filter_resource_ids=[customer.id],
            filter_date_range=(
                datetime.datetime.now(tz=tz) + datetime.timedelta(hours=-1),
                datetime.datetime.now(tz=tz),
            ),
            limit=6,
            offset=0,
        )
        assert len(audit_records) > 0, (
            f"Expected changes to be collected in the audit change buffer. Found {len(audit_records)} changes."
        )

        for record in audit_records:
            assert isinstance(record, SQLAuditRecord), (
                "Expected record to be an instance of SQLAuditRecord."
            )

            assert record.resource_id in [str(customer.id)], (
                f"Unexpected resource_id {record.resource_id} in audit record."
            )

            assert record.changed_by == str(test_user.user_id), (
                f"Expected changed_by to be {test_user.user_id}, got {record.changed_by}."
            )

            required_fields = [
                "name",
                "email",
                "created_by_user_id",
                "rating",
                "barcode",
                "created_at",
            ]
            assert len(required_fields) == len(record.changes), (
                f"Unexpected number of changes for record {record.record_id}: {len(record.changes)}"
            )

            for field in required_fields:
                assert any(change.field_name == field for change in record.changes), (
                    f"Expected change for field {field} in record {record.record_id}."
                )

            for change in record.changes:
                print(change)
                assert isinstance(change, SQLAuditChange), (
                    "Expected change to be an instance of AuditChange."
                )
                assert change.field_name in required_fields, (
                    f"Unexpected field {change.field_name} in change."
                )

