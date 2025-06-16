import uuid
from sqlalchemy import JSON, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
    relationship,
)

from sqlaudit.config import SQLAuditConfig, set_config
from sqlaudit.context import AuditContextManager
from sqlaudit.decorators import track_table
from sqlaudit.hooks import register_hooks
from sqlaudit.retrieval import get_resource_changes


# Create an in-memory SQLite database
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Helper function to get a database session.
    This function is used to provide a database session to the application.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    """
    Base class for declarative class definitions.
    """

    pass


# Define the User model
class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, nullable=False)


# Create a user instance
user = User(username="jdoe")


def mocked_user_id_retrieval() -> int:
    """Mocked function to return the current user ID for audit tracking."""
    return 1


# Set the global audit configuration
config = SQLAuditConfig(
    session_factory=get_db,
    user_model=User,
    user_model_user_id_field="user_id",
    get_user_id_callback=mocked_user_id_retrieval,
)

# We set the configuration and register hooks for auditing
set_config(config)
register_hooks()


class CountryCode(Base):
    """
    CountryCode model representing country codes in the system.
    This is a simple model to demonstrate the basic functionality of SQLAudit.
    """

    __tablename__ = "country_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, nullable=False)


# Define the Customer model with tracked fields for auditing
@track_table(
    # tracked_fields=[
    #     "customer_id",
    #     "name",
    #     "email",
    #     "user_id",
    #     "age",
    #     "data",
    #     "is_active",
    # ],
    table_label="Customer",
)
class Customer(Base):
    """
    Customer model representing customers in the system.

    For demonstration purposes we include a some basic data types such as:
    - Integer
    - String
    - ForeignKey
    - JSON
    - Boolean
    This model is used to demonstrate the basic functionality of SQLAudit.
    """

    __tablename__ = "customers"

    customer_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    country_id: Mapped[int | None] = mapped_column(
        ForeignKey("country_codes.id"), nullable=True
    )

    county: Mapped[CountryCode | None] = relationship("CountryCode")


if __name__ == "__main__":
    # Create all tables in the database
    Base.metadata.create_all(engine)

    # Set up audit hooks before any tracked operations
    register_hooks()

    # Get a database session
    with next(get_db()) as session:
        # Add the user to the session and commit
        print("=== Adding mock user ===")
        session.add(user)
        session.commit()

        def add_customer(session, name, email, user_id, **kwargs):
            customer = Customer(name=name, email=email, user_id=user_id, **kwargs)
            session.add(customer)
            session.commit()
            print(
                f"Added customer {customer.customer_id} with name '{customer.name}' and email '{customer.email}'."
            )
            return customer

        print("\n=== Adding first customer (John Doe) ===")
        customer1 = add_customer(session, "John Doe", "jdoe@example.com", user.user_id)

        print("\n=== Adding second customer (Jane Doe) ===")
        customer2 = add_customer(session, "Jane Doe", "jane@example.com", user.user_id)

        # Modify customer with auditing context
        print("\n=== Modifying Jane Doe with AuditContextManager ===")
        with AuditContextManager(reason="blabla", impersonated_by="1"):
            customer2.email = "jane2@example.com"
            customer2.age = 30
            customer2.data = {"preferences": {"newsletter": True}}
            customer2.is_active = False
            session.flush()

        session.refresh(customer2)
        customer2.name = "Jane Smith"
        session.commit()
        print(f"Updated customer {customer2.customer_id} name to '{customer2.name}'.")

        print("\n=== Retrieving audit trail for Jane Smith ===")
        changes = get_resource_changes(
            model_class=Customer,
            session=session,
            filter_resource_ids=customer2.customer_id,
        )

        for change in changes:
            print(change.model_dump_json(indent=4) + "\n")
