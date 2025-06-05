from logging import getLogger

import pytest
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sqlaudit.exceptions import SQLAuditTableAlreadyRegisteredError
from sqlaudit._internals.registry import AuditRegistry
from sqlaudit.types import SQLAuditOptions

logger = getLogger(__name__)

def test_registry_addition():
    """
    Test the SQLAudit registry addition functionality.
    This test checks if the registry correctly registers new models and tracks changes.
    """

    registry = AuditRegistry()  # We create a local instance of the registry for testing

    class Base(DeclarativeBase):
        pass

    class Customer(Base):
        __tablename__ = "customer"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()
        email: Mapped[str] = mapped_column()
        created_by_user_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))

    options: SQLAuditOptions = SQLAuditOptions(
        tracked_fields=["name", "email", "created_by_user_id"],
    )

    # Register the model with the registry
    registry.register(Customer, options)

    assert Customer in registry, "Customer model should be registered in the registry."


def test_registry_faulty_addition_add_twice():
    """
    Test the SQLAudit registry faulty addition functionality.
    This test checks if the registry raises an error when trying to register a model without required fields.
    """

    registry = AuditRegistry()  # We create a local instance of the registry for testing

    class Base(DeclarativeBase):
        pass

    class Customer(Base):
        __tablename__ = "customer"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()
        email: Mapped[str] = mapped_column()
        created_by_user_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))

    options: SQLAuditOptions = SQLAuditOptions(
        tracked_fields=["name", "email", "created_by_user_id"],
    )

    # We register the model with the registry twice to check if it raises an error
    registry.register(Customer, options)

    with pytest.raises(SQLAuditTableAlreadyRegisteredError):
        registry.register(Customer, options)


def test_registry_faulty_addition_not_declarative_base():
    """
    Test the SQLAudit registry faulty addition functionality.
    This test checks if the registry raises an error when trying to register a model that is not a DeclarativeBase subclass.
    """

    registry = AuditRegistry()  # We create a local instance of the registry for testing

    class NotDeclarativeBase:
        __tablename__ = "not_declarative_base"

    options: SQLAuditOptions = SQLAuditOptions(
        tracked_fields=["field1", "field2"],
    )

    # We try to register a model that is not a DeclarativeBase subclass
    with pytest.raises(TypeError):
        registry.register(NotDeclarativeBase, options)  # type: ignore


def test_registry_faulty_get_unregistered_model():
    """
    Test the SQLAudit registry faulty get functionality.
    This test checks if the registry raises an error when trying to get a model that is not registered.
    """

    registry = AuditRegistry()  # We create a local instance of the registry for testing

    class Base(DeclarativeBase):
        pass

    class UnregisteredModel(Base):
        __tablename__ = "unregistered_model"
        id: Mapped[int] = mapped_column(primary_key=True)

    # We try to get a model that is not registered
    with pytest.raises(KeyError):
        _ = registry.get(UnregisteredModel)
