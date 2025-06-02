from dataclasses import dataclass

from sqlalchemy.orm import DeclarativeBase

from .exceptions import SQLAuditTableAlreadyRegisteredError
from sqlaudit.logger import logger



@dataclass
class SQLAuditOptions:
    tracked_fields: list[str]
    record_id_field: str | None = None
    user_id_field: str | None = None
    table_label: str | None = None

    def __post_init__(self):
        if not isinstance(self.tracked_fields, list) or not all(
            isinstance(field, str) for field in self.tracked_fields
        ):
            raise TypeError(
                "SQLAuditOptions.tracked_fields must be a list[str]. Got %r."
                % type(self.tracked_fields).__name__
            )
        if (
            not isinstance(self.record_id_field, str)
            and self.record_id_field is not None
        ):
            raise TypeError(
                "SQLAuditOptions.record_id_field must be a 'str' or 'None'. Got %r."
                % type(self.record_id_field).__name__
            )

        if self.user_id_field is not None and not isinstance(self.user_id_field, str):
            raise TypeError(
                "SQLAuditOptions.user_id_field must be a 'str' or 'None'. Got %r."
                % type(self.user_id_field).__name__
            )

        if self.table_label is not None and not isinstance(self.table_label, str):
            raise TypeError(
                "SQLAuditOptions.table_label must be a 'str' or 'None'. Got %r."
                % type(self.table_label).__name__
            )


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
