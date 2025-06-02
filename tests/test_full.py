import datetime
import uuid

import pytest
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from tzlocal import get_localzone, get_localzone_name

from sqlaudit.config import (
    SQLAuditConfig,
    clear_config,
    set_config,
)
from sqlaudit.decorators import track_table
from sqlaudit.hooks import register_hooks
from sqlaudit.retrieval import SQLAuditRecord, get_resource_changes
from sqlaudit.utils import get_user_id_from_instance
from tests.utils.db import create_user_model


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


def test_full_audit_flow(SessionLocal: sessionmaker):
    """
    Test the full audit flow including configuration, buffer management, and change registration.
    This test checks if the audit system correctly collects and processes changes.
    """

    # Clear any existing configuration
    clear_config()

    # Create a user model
    class Base(DeclarativeBase):
        pass

    User = create_user_model(Base)

    test_user = User(
        user_id=1,
        first_name="John",
        last_name="Doe",
        email="jdoe@example.com",
    )

    # We create a model instance to test with

    @track_table(
        tracked_fields=["name", "email", "created_by_user_id"],
        user_id_field="created_by_user_id",
    )
    class Customer(Base):
        __tablename__ = "customer"
        id: Mapped[str] = mapped_column(
            default=lambda: str(uuid.uuid4()), primary_key=True
        )
        name: Mapped[str] = mapped_column()
        email: Mapped[str] = mapped_column()
        created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))

    config = SQLAuditConfig(
        session_factory=lambda: get_db(SessionLocal),
        user_model=User,
        user_model_user_id_field="user_id",
        get_user_id_callback=lambda: get_user_id_from_instance(test_user, "user_id"),
    )

    set_config(config)

    # We have to register the hooks
    register_hooks()

    with next(get_db(SessionLocal)) as session:
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

        customer2 = Customer(
            name="John Doe",
            email="johndoe@example.com",
            created_by_user_id=test_user.user_id,
        )

        # Add the second customer to the session
        session.add(customer2)
        session.commit()

        session.refresh(customer)
        session.refresh(customer2)

        # At this point, the audit change buffer should have collected changes

        tz = get_localzone()
        changes = get_resource_changes(
            Customer,
            filter_resource_ids=[customer2.id, customer.id],
            filter_date_range=(
                datetime.datetime.now(tz=tz) + datetime.timedelta(hours=-1),
                datetime.datetime.now(tz=tz),
            ),
            limit=6,
            offset=0,
        )
        assert len(changes) > 0, (
            f"Expected changes to be collected in the audit change buffer. Found {len(changes)} changes."
        )

        for change in changes:
            assert isinstance(change, SQLAuditRecord), (
                "Expected change to be an instance of AuditChange."
            )
            assert change.field_name in ["name", "email", "created_by_user_id"], (
                f"Unexpected field {change.field_name} in change."
            )
            assert change.old_value is not None, "Expected old_value to be set."
            assert change.new_value is not None, "Expected new_value to be set."
