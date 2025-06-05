from dataclasses import dataclass

from sqlalchemy.orm import DeclarativeBase

from sqlaudit._internals.logger import logger
from sqlaudit.exceptions import SQLAuditTableAlreadyRegisteredError
from sqlaudit.types import SQLAuditOptions


@dataclass
class AuditTableEntry:
    table_model: type[DeclarativeBase]
    options: SQLAuditOptions


class AuditRegistry:
    def __init__(self):
        self._registry: dict[str, AuditTableEntry] = {}

    def register(self, table_model: type[DeclarativeBase], options: SQLAuditOptions):
        """
        Register a table model and its options for auditing.
        """
        table_name = table_model.__tablename__
        if table_name in self._registry:
            raise SQLAuditTableAlreadyRegisteredError(table_name)

        if not issubclass(table_model, DeclarativeBase):
            raise TypeError(
                f"Table model {table_model.__name__} must be a subclass of DeclarativeBase. Are you using this decorator on a SQLAlchemy model?"
            )
        
        self._registry[table_name] = AuditTableEntry(
            table_model=table_model, options=options
        )

        logger.debug(
            "Registered table model %s with options: %s",
            table_model.__name__,
            options,
        )

    def __contains__(self, model_class: type[DeclarativeBase]) -> bool:
        """
        Check if a table model is registered for auditing.
        """
        return model_class.__tablename__ in self._registry

    def get(self, model: type[DeclarativeBase] | DeclarativeBase) -> AuditTableEntry:
        """
        Get the registered options for a table model.
        """
        if isinstance(model, DeclarativeBase):
            model = type(model)

        table_name = model.__tablename__
        if table_name not in self._registry:
            raise KeyError(f"Table {table_name} is not registered for auditing.")
        
        return self._registry[table_name]

audit_model_registry = AuditRegistry()
