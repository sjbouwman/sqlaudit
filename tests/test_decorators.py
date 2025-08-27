import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, mapped_column, Mapped
from sqlaudit.decorators import track_table
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
   


def test_decorator(db_session):
    _, Base = db_session

    @track_table(tracked_fields=["name", "email", "created_by_user_id"])
    class Customer(Base):
        __tablename__ = "customer"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()
        email: Mapped[str] = mapped_column()
        created_by_user_id: Mapped[int] = mapped_column()



def test_decorator_wrong_tracked_fields_type(db_session):
    _, Base = db_session

    with pytest.raises(TypeError):
        @track_table(tracked_fields="name")  # type: ignore
        class Customer(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()



def test_decorator_with_wrong_user_id_field_type(db_session):
    _, Base = db_session

    with pytest.raises(TypeError):
        @track_table(tracked_fields=["name"], user_id_field=123)  # type: ignore
        class Customer(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()



def test_decorator_with_wrong_resource_id_field_type(db_session):
    _, Base = db_session

    with pytest.raises(TypeError):
        @track_table(tracked_fields=["name"], resource_id_field=123)  # type: ignore
        class Customer(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()



def test_decorator_with_wrong_table_label_type(db_session):
    _, Base = db_session

    with pytest.raises(TypeError):
        @track_table(tracked_fields=["name"], table_label=123)  # type: ignore
        class Customer(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()



def test_decorator_auto_tracked_fields(db_session):
    _, Base = db_session

    @track_table()
    class Customer(Base):
        __tablename__ = "customer"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()
        email: Mapped[str] = mapped_column()
        created_by_user_id: Mapped[int] = mapped_column()



def test_decorator_not_existing_tracked_field(db_session):
    _, Base = db_session

    with pytest.raises(ValueError):
        @track_table(tracked_fields=["non_existing_field"])
        class CustomerWrongField(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()

def test_decorator_with_table_label(db_session):
    _, Base = db_session

    @track_table(tracked_fields=["name", "email", "created_by_user_id"], table_label="Customer")
    class Customer(Base):
        __tablename__ = "customer"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()
        email: Mapped[str] = mapped_column()
        created_by_user_id: Mapped[int] = mapped_column()

def test_decorator_with_invalid_table_label(db_session):
    _, Base = db_session

    # Should raise a TypeError


    with pytest.raises(TypeError):
        @track_table(tracked_fields=["name", "email", "created_by_user_id"], table_label=123)
        class Customer(Base):
            __tablename__ = "customer"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column()
            email: Mapped[str] = mapped_column()
            created_by_user_id: Mapped[int] = mapped_column()