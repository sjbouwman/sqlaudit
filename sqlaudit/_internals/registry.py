from dataclasses import dataclass
from typing import Any, get_args

from sqlalchemy import Column, inspect
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty

from sqlaudit._internals.logger import logger
from sqlaudit.exceptions import SQLAuditTableAlreadyRegisteredError
from sqlaudit.serializer import Serializer
from sqlaudit.types import SQLAuditOptions


def _get_trackable_fields(table_model: type[DeclarativeBase]) -> list[Column[Any]]:
    """
    Get the trackable fields for the given table model. Trackable fields are all columns that are not relationship properties.
    """
    return [x for x in inspect(table_model).c if not isinstance(x, RelationshipProperty)]

def _get_trackable_field_names(table_model: type[DeclarativeBase]) -> list[str]:
    """
    Discover fields in the table model that are trackable for auditing. Trackable fields are all columns that are not relationship properties.
    """
    return [x.name for x in _get_trackable_fields(table_model)]


def _validate_tracked_fields(
    table_model: type[DeclarativeBase],
    tracked_fields: list[str],
    trackable_fields: list[str],
) -> None:
    """
    Validate that the tracked fields are valid columns in the table model.
    """
    # We make sure that we can serialize and deserialize all the tracked fields
    available_fields = _get_trackable_fields(table_model)

    for field in available_fields:
        if field.name not in tracked_fields:
            continue

        annotations = table_model.__annotations__.get(field.name)
        if not annotations  :
            raise ValueError(
                f"Field '{field.name}' is not annotated in the model {table_model.__name__}."
            )
        
        try:
            inner_type = get_args(annotations)[0]
        except IndexError:
            raise ValueError(
                "Field %r in model %s is not a valid type. Could not determine inner type. Outer type is %r"
                % (field.name, table_model.__name__, get_args(annotations))
            )

        if not Serializer.has_handler(inner_type):
            raise ValueError(
                f"Field '{field.name}' in model {table_model.__name__} is of type {inner_type} which is not a known type. Please register a serializer for this type using `Serializer.register_custom_handler()`."
            )

    if tracked_fields and trackable_fields is None:
        raise ValueError(
            "Field %r is not a valid field in the model %s. No trackable fields (non-relationship columns) found."
            % (tracked_fields, table_model.__name__)
        )

    if not tracked_fields:
        logger.debug(
            "tracked_fields is empty for table model %s. Using all trackable fields: %s",
            table_model.__name__,
            trackable_fields,
        )
        return

    for field in tracked_fields:
        logger.debug(
            "Validating tracked field '%s' for table model %s",
            field,
            table_model.__name__,
        )
        if field not in trackable_fields:
            raise ValueError(
                f"Field '{field}' is not a valid field in the model {table_model.__name__}. "
                "Is it a valid column name, or is it a relationship field?"
            )


@dataclass
class AuditTableEntry:
    table_model: type[DeclarativeBase]
    options: SQLAuditOptions
    trackable_fields: list[str]


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

        trackable_field_names = _get_trackable_field_names(table_model)

        _validate_tracked_fields(
            table_model=table_model,
            tracked_fields=options.tracked_fields or [],
            trackable_fields=trackable_field_names,
        )

        self._registry[table_name] = AuditTableEntry(
            table_model=table_model, options=options, trackable_fields=trackable_field_names
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
    
    def clear(self):
        """
        Clear all registered table models from the audit registry.
        """
        self._registry.clear()

    def from_table_name(self, table_name: str) -> AuditTableEntry:
        """
        Get the registered options for a table model by its table name.
        """
        if table_name not in self._registry:
            raise KeyError(f"Table {table_name} is not registered for auditing.")

        return self._registry[table_name]


audit_model_registry = AuditRegistry()
