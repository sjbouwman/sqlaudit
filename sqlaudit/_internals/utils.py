import uuid
import warnings
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase, Query, Session
from sqlalchemy.sql.schema import ForeignKey

from sqlaudit._internals.logger import logger
from sqlaudit._internals.models import (
    SQLAuditLog,
    SQLAuditLogField,
    SQLAuditLogFieldChange,
    SQLAuditLogTable,
)
from sqlaudit._internals.registry import audit_model_registry
from sqlaudit._internals.types import AuditChange, LogContextInternal
from sqlaudit.config import SQLAuditConfig, get_config
from sqlaudit.exceptions import SQLAuditTableNotInDatabaseError, SQLAuditUserConfigError
from sqlaudit.types import ResourceIdType


def column_is_foreign_key_of(
    table: type[DeclarativeBase],
    column_name: str,
    foreign_table_name: str,
    foreign_column_name: str,
) -> bool:
    """
    Check if the specified column in the table has a foreign key constraint.

    Args:
        table (type[DeclarativeBase]): The SQLAlchemy table model.
        column_name (str): The name of the column to check.

    Returns:
        bool: True if the column has a foreign key, False otherwise.
    """
    column = getattr(table, column_name)

    foreign_keys: tuple[ForeignKey] = cast(
        tuple[ForeignKey], getattr(column, "foreign_keys", ())
    )

    if not foreign_keys:
        return False

    for fk in foreign_keys:
        if fk.target_fullname == f"{foreign_table_name}.{foreign_column_name}":
            return True

    return False


def get_primary_keys(table: type[DeclarativeBase]) -> list[str]:
    """
    Retrieves the primary key fields of a SQLAlchemy table.

    Args:
        table (type[DeclarativeBase]): The SQLAlchemy table class.

    Returns:
        list[str]: A list of primary key field names.
    """
    primary_keys = inspect(table).primary_key
    if not primary_keys:
        raise ValueError(f"Table {table.__name__} has no primary key defined.")

    return [pk.name for pk in primary_keys]


def get_user_id_from_instance(
    instance: DeclarativeBase, user_id_field: str
) -> str | None:
    """
    Extracts the user ID from the given object based on the specified user ID field.
    If the field is not set, returns None.
    """
    if user_id_field is None or not hasattr(instance, user_id_field):
        raise ValueError(f"Instance does not have the user_id field '{user_id_field}'.")

    user_id = getattr(instance, user_id_field, None)
    if user_id is None:
        return None

    return str(user_id) if isinstance(user_id, (str, int)) else None


def add_audit_log(
    resource_id: str,
    table: SQLAuditLogTable,
    context: LogContextInternal,
    session: Session,
):
    """
    Adds an audit log entry to the database.
    """
    assert isinstance(resource_id, str), (
        "resource_id must be a string, got %s" % type(resource_id).__name__
    )
    audit_log_db = SQLAuditLog(resource_id=resource_id, table=table, **context.dump())
    session.add(audit_log_db)
    return audit_log_db


def add_audit_change(
    field: SQLAuditLogField,
    log: SQLAuditLog,
    change: AuditChange,
    session: Session,
):
    """
    Adds a change entry to the audit log for a specific field.
    """
    field_change_db = SQLAuditLogFieldChange(
        field=field,
        audit_log=log,
        old_value=change.old_value,
        new_value=change.new_value,
    )

    session.add(field_change_db)
    return field_change_db


def table_exists(session: Session, table_name: str) -> bool:
    """
    Checks if a table exists in the database.
    """
    inspector = inspect(session.get_bind())
    return table_name in inspector.get_table_names()


def build_field_map(
    fields: list[SQLAuditLogField],
) -> dict[int, SQLAuditLogField]:
    """
    Build a mapping of field_id to SQLAuditLogField objects for quick access.
    """
    return {field.field_id: field for field in fields}


def get_audit_log_table(session: Session, table_name: str):
    return session.query(SQLAuditLogTable).filter_by(table_name=table_name).first()


def get_audit_log_fields_by_table_id(session: Session, table_id: int):
    return session.query(SQLAuditLogField).filter_by(table_id=table_id).all()


def logs_users_enabled(config: SQLAuditConfig) -> bool:
    return config.user_model is not None and config.user_model_user_id_field is not None


def get_table_model(model_class: type[DeclarativeBase]):
    return audit_model_registry.get(model=model_class).table_model


def get_filtered_audit_fields(
    session: Session, table_id: int, filter_fields: str | list[str] | None
):
    fields = get_audit_log_fields_by_table_id(session, table_id)

    if filter_fields is not None:
        if isinstance(filter_fields, str):
            filter_fields = [filter_fields]
        fields = [field for field in fields if field.field_name in filter_fields]

    return fields


def ensure_valid_resource_ids(
    value: ResourceIdType | list[ResourceIdType] | None,
) -> list[str]:
    if value is None:
        return []

    if isinstance(value, (str, int, uuid.UUID)):
        value = [str(value)]

    elif not isinstance(value, list):
        raise TypeError(
            f"filter_resource_ids must be a list, str, int, or uuid.UUID, got {type(value)}"
        )

    if not all(isinstance(v, (str, int, uuid.UUID)) for v in value):
        raise TypeError(
            "All items in filter_resource_ids must be str, int, or uuid.UUID."
        )

    return [str(v) for v in value if v is not None and v != ""]


def get_audit_log_table_or_raise(session: Session, table_name: str):
    audit_log_table = get_audit_log_table(session, table_name)
    if audit_log_table is None:
        raise SQLAuditTableNotInDatabaseError()
    return audit_log_table


def normalize_datetime_range(
    filter_date_range: tuple[datetime | None, datetime | None],
    config: SQLAuditConfig,
) -> tuple[datetime | None, datetime | None]:
    """
    Normalize a date range to ensure both start and end dates are timezone-aware.
    """

    start_date, end_date = filter_date_range
    invalid_tz_parameters: list[str] = []
    if start_date:
        if start_date.tzinfo is None:
            invalid_tz_parameters.append("start_date")

            start_date = start_date.replace(tzinfo=config._user_tz)

        if start_date.tzinfo != UTC:
            start_date = start_date.astimezone(UTC)

    if end_date:
        if end_date.tzinfo is None:
            invalid_tz_parameters.append("end_date")

            end_date = end_date.replace(tzinfo=config._user_tz)

        if end_date.tzinfo != UTC:
            end_date = end_date.astimezone(UTC)

    if invalid_tz_parameters:
        warnings.warn(
            f"The following parameters were timezone naive: {', '.join(invalid_tz_parameters)}. "
            "They have been assumed to be in the system timezone and converted to UTC. "
            "For accurate results, explicitly provide a timezone aware datetime objects.",
            UserWarning,
        )

    if start_date and end_date and start_date > end_date:
        raise ValueError(
            "start_date cannot be after end_date. Please check the provided date range."
        )

    return start_date, end_date


def build_audit_query(
    session: Session,
    field_ids: list[int],
    filter_resource_ids: list[str] | None,
    filter_date_range: tuple[datetime | None, datetime | None] | None,
    filter_user_ids: ResourceIdType | list[ResourceIdType] | None,
    logs_users: bool,
):
    config = get_config()
    query = (
        session.query(SQLAuditLog)
        .join(SQLAuditLogFieldChange)
        .filter(SQLAuditLogFieldChange.field_id.in_(field_ids))
    )

    if filter_resource_ids and len(filter_resource_ids) > 0:
        query = query.filter(SQLAuditLog.resource_id.in_(filter_resource_ids))

    if filter_date_range is not None:
        start_date, end_date = normalize_datetime_range(filter_date_range, config)

        logger.debug(
            "Filtering audit logs by date range: %s to %s", start_date, end_date
        )
        if start_date:
            query = query.filter(SQLAuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(SQLAuditLog.timestamp <= end_date)

    if filter_user_ids is not None:
        if not logs_users:
            raise SQLAuditUserConfigError()

        if isinstance(filter_user_ids, str):
            filter_user_ids = [filter_user_ids]

        if isinstance(filter_user_ids, (int, uuid.UUID)) and not isinstance(
            filter_user_ids, list
        ):
            filter_user_ids = [str(filter_user_ids)]

        if not isinstance(filter_user_ids, list):
            raise TypeError(
                f"filter_user_ids must be a list, str, int, or uuid.UUID, got {type(filter_user_ids)}"
            )

        query = query.filter(SQLAuditLog.changed_by.in_(filter_user_ids))

    return query


def apply_sorting(
    query: Query[SQLAuditLog],
    sort_by: str | None,
    sort_direction: Literal["asc", "desc"] = "desc",
):
    """
    Apply sorting to the query based on the provided sort_by and sort_direction.
    """

    sort_attribute = getattr(SQLAuditLog, sort_by) if sort_by else SQLAuditLog.timestamp
    if sort_direction not in ("asc", "desc"):
        raise ValueError(
            f"Invalid sort direction: {sort_direction}. Must be 'asc' or 'desc'."
        )

    query = query.order_by(
        sort_attribute.asc() if sort_direction == "asc" else sort_attribute.desc()
    )

    return query
