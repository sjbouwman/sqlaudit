import pytest
from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from sqlaudit.utils import (
    column_is_foreign_key_of,
    get_primary_keys,
    get_user_id_from_instance,
    table_exists,
)

from .utils.db import create_user_model


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


def test_table_exists(SessionLocal: sessionmaker):
    """
    Test the SQLAudit.utils.table_exists function.
    This test checks if the table_exists function correctly identifies the existence of a table.
    """

    class Base(DeclarativeBase):
        pass

    User = create_user_model(Base)

    # session = get_db(SessionLocal)
    with next(get_db(SessionLocal)) as session:
        # Table should first not exist
        assert not table_exists(session, User.__tablename__), (
            f"Table {User.__tablename__} should not exist at this point."
        )

        # Create the table
        Base.metadata.create_all(bind=session.get_bind())

        # Now the table should exist
        assert table_exists(session, User.__tablename__), (
            f"Table {User.__tablename__} should exist at this point."
        )


def test_get_primary_keys(SessionLocal: sessionmaker):
    """
    Test the SQLAudit.utils.get_primary_keys function.
    This test checks if the get_primary_keys function correctly retrieves primary keys from a table.
    """

    class Base(DeclarativeBase):
        pass

    User = create_user_model(Base)

    with next(get_db(SessionLocal)) as session:
        # Create the table
        Base.metadata.create_all(bind=session.get_bind())

        # Get primary keys
        primary_keys = get_primary_keys(User)

        assert primary_keys == ["user_id"], (
            f"Expected primary keys ['user_id'], but got {primary_keys}."
        )


def test_get_primary_keys_multiple_primary_keys(SessionLocal: sessionmaker):
    """
    Test the SQLAudit.utils.get_primary_keys function with a model that has multiple primary keys.
    This test checks if the function correctly retrieves all primary keys from a table with composite primary keys.
    """

    class Base(DeclarativeBase):
        pass

    class SomeOtherModel(Base):
        __tablename__ = "some_other_model"
        id: Mapped[int] = mapped_column(primary_key=True)
        secondary_key: Mapped[str] = mapped_column(String(32), primary_key=True)

    with next(get_db(SessionLocal)) as session:
        # Create the table
        Base.metadata.create_all(bind=session.get_bind())

        # Get primary keys
        primary_keys = get_primary_keys(SomeOtherModel)

        assert primary_keys == ["id", "secondary_key"], (
            f"Expected primary keys ['id', 'secondary_key'], but got {primary_keys}."
        )


def test_get_user_id_from_instance(SessionLocal: sessionmaker):
    """
    Test the SQLAudit.utils.get_user_id_from_instance function.
    This test checks if the function correctly extracts the user ID from an instance of a model.
    """

    class Base(DeclarativeBase):
        pass

    User = create_user_model(Base)

    user = User(
        user_id=3821, first_name="John", last_name="Doe", email="jdoe@example.com"
    )

    with next(get_db(SessionLocal)) as session:
        # Create the table
        Base.metadata.create_all(bind=session.get_bind())

        # Get user ID from instance
        user_id = get_user_id_from_instance(user, "user_id")

        assert user_id == "3821", f"Expected user ID '3821', but got {user_id}."

        # Test with a non-existent field
        with pytest.raises(
            ValueError,
            match="Instance does not have the user_id field 'non_existent_field'.",
        ):
            get_user_id_from_instance(user, "non_existent_field")


def test_column_is_foreign_key(SessionLocal: sessionmaker):
    """
    Test the SQLAudit.utils.column_is_foreign_key function.
    This test checks if the function correctly identifies a column as a foreign key.
    """

    class Base(DeclarativeBase):
        pass

    User = create_user_model(Base)

    class Customer(Base):
        __tablename__ = "customers"
        customer_id: Mapped[int] = mapped_column(primary_key=True)
        created_by_user_id: Mapped[int] = mapped_column(
            ForeignKey("users.user_id"), nullable=False
        )

    is_foreign_key = column_is_foreign_key_of(
        table=Customer,
        column_name="created_by_user_id",
        foreign_table_name=User.__tablename__,
        foreign_column_name="user_id",
    )
    
    assert is_foreign_key, (
        "The column 'created_by_user_id' should be a foreign key to 'users.user_id'."
    )

def test_column_is_not_foreign_key(SessionLocal: sessionmaker):
    """
    Test the SQLAudit.utils.column_is_foreign_key function with a column that is not a foreign key.
    This test checks if the function correctly identifies a column that is not a foreign key.
    """

    class Base(DeclarativeBase):
        pass

    User = create_user_model(Base)

    class Customer(Base):
        __tablename__ = "customers"
        customer_id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(String)

    is_foreign_key = column_is_foreign_key_of(
        table=Customer,
        column_name="name",
        foreign_table_name=User.__tablename__,
        foreign_column_name="user_id",
    )
    
    assert not is_foreign_key, (
        "The column 'name' should not be a foreign key to 'users.user_id'."
    )