import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, mapped_column, Mapped

from sqlaudit.config import (
    clear_config,
)
from sqlaudit.decorators import track_table


@pytest.fixture(scope="function")
def SessionLocal():
    """Fixture to create a new SQLAlchemy session for each test."""

    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield SessionLocal

def test_decorator(SessionLocal: sessionmaker):
    """
    Test the SQLAudit decorators functionality.
    This test checks if the decorators correctly register changes and handle user information.
    """

    # Clear any existing configuration
    clear_config()

    # Create a user model
    class Base(DeclarativeBase):
        pass
    

    @track_table(tracked_fields=["name", "email", "created_by_user_id"])
    class Customer(Base):
        __tablename__ = "customer"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()



def test_decorator_wrong_tracked_fields_type(SessionLocal: sessionmaker):
    """
    Test the SQLAudit decorators with incorrect tracked_fields type.
    This test checks if the decorator raises an error when tracked_fields is not a list.
    """

    class Base(DeclarativeBase):
        pass

    with pytest.raises(TypeError, match="tracked_fields must be a list"):
        @track_table(tracked_fields="name") # type: ignore
        class Customer(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()


def test_decorator_with_wrong_user_id_field_type(SessionLocal: sessionmaker):
    """
    Test the SQLAudit decorators with incorrect user_id_field type.
    This test checks if the decorator raises an error when user_id_field is not a string.
    """

    class Base(DeclarativeBase):
        pass 

    with pytest.raises(TypeError):
        @track_table(tracked_fields=["name"], user_id_field=123)  # type: ignore
        class Customer(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()

def test_decorator_with_wrong_record_id_field_type(SessionLocal: sessionmaker):
    """
    Test the SQLAudit decorators with incorrect record_id_field type.
    This test checks if the decorator raises an error when record_id_field is not a string.
    """

    class Base(DeclarativeBase):
        pass

    with pytest.raises(TypeError):
        @track_table(tracked_fields=["name"], record_id_field=123)  # type: ignore
        class Customer(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()



def test_decorator_with_wrong_table_label_type(SessionLocal: sessionmaker):
    """
    Test the SQLAudit decorators with incorrect table_label type.
    This test checks if the decorator raises an error when table_label is not a string.
    """

    class Base(DeclarativeBase):
        pass

    with pytest.raises(TypeError):
        @track_table(tracked_fields=["name"], table_label=123)  # type: ignore
        class Customer(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()
    

