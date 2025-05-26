from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import DeclarativeBase

from sqlaudit.config import get_audit_config
from sqlaudit.options import SQLAuditOptionsBase
from sqlaudit.pre_flight import run_preflight

T = TypeVar("T", bound=DeclarativeBase)


def track_table(
    *,
    tracked_fields: list[str],
    record_id_field: str | None = None,
    user_id_field: str | None = None,
    table_label: str | None = None,
) -> Callable[[type[T]], type[T]]:
    config = get_audit_config()

    def decorator(cls: type[T]) -> type[T]:
        run_preflight(
            cls,
            SQLAuditOptionsBase(
                tracked_fields=tracked_fields,
                record_id_field=record_id_field,
                user_id_field=user_id_field or config.default_user_id_column,
                table_label=table_label,
            ),
        )

        if not issubclass(cls, DeclarativeBase):
            raise TypeError(
                f"@track_table can only be applied to classes that are subclasses of DeclarativeBase. Got {type(cls)}."
            )

        return cls

    return decorator
