from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import DeclarativeBase
from sqlaudit.registry import SQLAuditOptions, audit_model_registry

T = TypeVar("T", bound=DeclarativeBase)

def track_table(
    *,
    tracked_fields: list[str],
    record_id_field: str | None = None,
    user_id_field: str | None = None,
    table_label: str | None = None,
) -> Callable[[type[T]], type[T]]:
    options = SQLAuditOptions(
        tracked_fields=tracked_fields,
        record_id_field=record_id_field,
        user_id_field=user_id_field,
        table_label=table_label,
    )

    def decorator(cls: type[T]) -> type[T]:
        if cls not in audit_model_registry:
            audit_model_registry.register(table_model=cls, options=options)

        return cls

    return decorator
