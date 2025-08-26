from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import DeclarativeBase
from sqlaudit._internals.registry import audit_model_registry
from sqlaudit.types import SQLAuditOptions

T = TypeVar("T", bound=DeclarativeBase)


def track_table(
    *,
    tracked_fields: list[str] | None = None,
    resource_id_field: str | None = None,
    user_id_field: str | None = None,
    table_label: str | None = None,
) -> Callable[[type[T]], type[T]]:
    """
    Decorator to register a SQLAlchemy table model for auditing.
    This decorator registers the specified table model with the SQLAudit system,
    allowing it to track changes to the specified fields.
    Args:
        tracked_fields (list[str] | None): A list of field names to track changes for. If None, all trackable fields will be tracked.
        resource_id_field (str | None): The name of the field that uniquely identifies the resource.
        user_id_field (str | None): The name of the field that identifies the user making changes.
        table_label (str | None): A label for the table, used for display purposes.
    Returns:
        Callable[[type[T]], type[T]]: A decorator that registers the table model with SQLAudit.

    Usage:
    @track_table(
        tracked_fields=["name", "email"],
        resource_id_field="id",
        user_id_field="user_id",
        table_label="User Table"
    )  

    Note:
        - The `tracked_fields` must be a list of strings representing the field names to track.
        - The `resource_id_field` and `user_id_field` are optional and can be set to None if not needed.
        - The `table_label` is also optional and can be used for better readability in logs.
    """
    options = SQLAuditOptions(
        tracked_fields=tracked_fields,
        resource_id_field=resource_id_field,
        user_id_field=user_id_field,
        table_label=table_label,
    )

    def decorator(cls: type[T]) -> type[T]:
        if cls not in audit_model_registry:
            audit_model_registry.register(table_model=cls, options=options)

        return cls

    return decorator


__all__ = ["track_table"]
