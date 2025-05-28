from sqlalchemy import ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from sqlaudit.config import SQLAuditConfig, set_config
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
    """
    User model representing users in the system.
    """

    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Add more columns as needed


# Create a user instance
user = User()


def get_user_id_from_instance() -> int:
    """
    Returns the user_id from the instance.
    This function is used to retrieve the user ID for auditing purposes.
    """
    return user.user_id


# Set the global audit configuration
config = SQLAuditConfig(
    session_factory=get_db,
    user_model=User,
    user_model_user_id_field="user_id",
    get_user_id_callback=get_user_id_from_instance,
)
set_config(config)


# Define the Customer model with tracked fields for auditing
@track_table(tracked_fields=["name", "email", "user_id"], table_label="Customer")
class Customer(Base):
    """
    Customer model representing customers in the system.
    This model is tracked for changes in the specified fields.
    """

    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False)


if __name__ == "__main__":
    # Create all tables in the database
    Base.metadata.create_all(engine)

    # Get a database session
    with next(get_db()) as session:
        # Register hooks for auditing
        register_hooks()

        # Add the user to the session and commit
        session.add(user)
        session.commit()

        # Create and add a new customer
        new_customer = Customer(
            name="John Doe", email="jdoe@example.com", user_id=user.user_id
        )

        session.add(new_customer)
        session.commit()

        print(
            f"Customer {new_customer.customer_id} added with name {new_customer.name} and email {new_customer.email}."
        )

        # Check if the customer is in the database
        customer = (
            session.query(Customer)
            .filter_by(customer_id=new_customer.customer_id)
            .first()
        )

        # Create and add another customer
        new_customer2 = Customer(
            name="Jane Doe", email="jane@example.com", user_id=user.user_id
        )

        session.add(new_customer2)
        session.commit()

        print(
            f"Customer {new_customer2.customer_id} added with name {new_customer2.name} and email {new_customer2.email}."
        )

        # Refresh the session and update the customer's name so we have some more data to track
        session.refresh(new_customer2)
        new_customer2.name = "Jane Smith"
        session.commit()

        # Retrieve and print changes for the customers
        changes = get_resource_changes(
            model_class=Customer,
            session=session,
            filter_resource_ids=new_customer2.customer_id,
        )

        for change in changes:
            print(
                f"FIELD: '{change.field_name}' CHANGED AT {str(change.timestamp)} TO {change.new_value} (OLD: {change.old_value}) BY USER ID {change.changed_by}"
            )
