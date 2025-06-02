import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
import warnings

from pydantic import BaseModel, Field
from sqlalchemy.orm import DeclarativeBase, Session, Query

from sqlaudit.config import SQLAuditConfig, get_config
from sqlaudit.exceptions import (
    SQLAuditTableNotInDatabaseError,
    SQLAuditUserConfigError,
)
from sqlaudit.models import (
    SQLAuditLog,
    SQLAuditLogField,
    SQLAuditLogTable,
)
from sqlaudit.registry import audit_model_registry
from sqlaudit.logger import logger

type ResourceIdType = str | int | uuid.UUID


class SQLAuditRecord(BaseModel):
    """
    Represents a record in the audit log.
    """

    table_name: Annotated[
        str, Field(description="Name of the table where the change occurred")
    ]

    table_label: Annotated[
        str | None,
        Field(default=None, description="Label for the table (optional, can be None)"),
    ]

    resource_id: Annotated[str, Field(description="Primary key of the affected record")]

    field_name: Annotated[str, Field(description="Name of the field that was changed")]

    old_value: Annotated[
        list[str], Field(description="List of string values before the change")
    ]

    new_value: Annotated[
        list[str], Field(description="List of string values after the change")
    ]

    timestamp: Annotated[
        datetime, Field(description="Timestamp of when the change was made")
    ]

    changed_by: Annotated[
        Any | None,
        Field(
            default=None, description="ID of the user who made the change (optional)"
        ),
    ]


def _get_audit_log_table(session: Session, table_name: str):
    """
    Get the audit log table for a given table name.
    """
    return session.query(SQLAuditLogTable).filter_by(table_name=table_name).first()


def _get_audit_log_fields_by_table_id(session: Session, table_id: int):
    """
    Get all audit log fields for a given table ID.
    """

    return session.query(SQLAuditLogField).filter_by(table_id=table_id).all()


def _logs_users_enabled(config: SQLAuditConfig) -> bool:
    return config.user_model is not None and config.user_model_user_id_field is not None


def _get_table_model(model_class: type[DeclarativeBase]):
    sqlaudit_metadata = audit_model_registry.get(model=model_class)
    return sqlaudit_metadata.table_model


def _get_filtered_audit_fields(
    session: Session, table_id: int, filter_fields: str | list[str] | None
):
    fields = _get_audit_log_fields_by_table_id(session, table_id)

    if filter_fields is not None:
        if isinstance(filter_fields, str):
            filter_fields = [filter_fields]
        fields = [field for field in fields if field.field_name in filter_fields]

    return fields


def _ensure_valid_resource_ids(
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


def _build_field_map(
    fields: list[SQLAuditLogField],
) -> dict[int, SQLAuditLogField]:
    return {field.field_id: field for field in fields}


def _get_audit_log_table_or_raise(session: Session, table_name: str):
    audit_log_table = _get_audit_log_table(session, table_name)
    if audit_log_table is None:
        raise SQLAuditTableNotInDatabaseError()
    return audit_log_table


def _normalize_datetime_range(
    filter_date_range: tuple[datetime | None, datetime | None],
    config: SQLAuditConfig,
) -> tuple[datetime | None, datetime | None]:
    """
    Normalize the date range to ensure both start and end dates are timezone-aware.
    If a date is None, it will be set to the current UTC time.
    """
    start_date, end_date = filter_date_range
    invalid_tz_parameters: list[str] = []
    if start_date:
        if start_date.tzinfo is None:
            if config.time_zone is None:
                invalid_tz_parameters.append("start_date")

            start_date = start_date.replace(tzinfo=config._user_tz)

        if start_date.tzinfo != UTC:
            start_date = start_date.astimezone(UTC)

    if end_date:
        if end_date.tzinfo is None:
            if config.time_zone is None:
                invalid_tz_parameters.append("end_date")

            end_date = end_date.replace(tzinfo=config._user_tz)

        if end_date.tzinfo != UTC:
            end_date = end_date.astimezone(UTC)

    if invalid_tz_parameters:
        warnings.warn(
            f"The following parameters were not timezone-aware: {', '.join(invalid_tz_parameters)}. "
            "They have been assumed to be in the system timezone and converted to UTC. "
            "For accurate results, explicitly provide a timezone in the SQLAuditConfig (time_zone) or use timezone aware datetime objects.",
            UserWarning,
        )

    if start_date and end_date and start_date > end_date:
        raise ValueError(
            "start_date cannot be after end_date. Please check the provided date range."
        )
    
    return start_date, end_date


def _build_audit_query(
    session: Session,
    field_ids: list[int],
    filter_resource_ids: list[str] | None,
    filter_date_range: tuple[datetime | None, datetime | None] | None,
    filter_user_ids: ResourceIdType | list[ResourceIdType] | None,
    logs_users: bool,
):
    config = get_config()
    query = session.query(SQLAuditLog).filter(SQLAuditLog.field_id.in_(field_ids))

    if filter_resource_ids and len(filter_resource_ids) > 0:
        query = query.filter(SQLAuditLog.record_id.in_(filter_resource_ids))

    if filter_date_range is not None:
        # We have to make sure that filter_date_range is a tuple of two datetime objects
        start_date, end_date = _normalize_datetime_range(filter_date_range, config)

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


def _build_change_records(
    audit_logs: list[SQLAuditLog],
    table_model: type[DeclarativeBase],
    audit_log_table: SQLAuditLogTable,
    field_lookup: dict[int, SQLAuditLogField],
) -> list[SQLAuditRecord]:
    def ensure_list_str(value: Any) -> list[str]:
        return [str(v) for v in value] if isinstance(value, list) else []

    config = get_config()
    user_id = config.get_user_id_callback() if config.get_user_id_callback else None

    return [
        SQLAuditRecord(
            table_name=table_model.__tablename__,
            resource_id=audit_log.record_id,
            field_name=field_lookup[audit_log.field_id].field_name,
            old_value=ensure_list_str(audit_log.old_value),
            new_value=ensure_list_str(audit_log.new_value),
            timestamp=audit_log.timestamp,
            changed_by=str(user_id) if user_id else None,
            table_label=audit_log_table.label or None,
        )
        for audit_log in audit_logs
    ]


def _apply_sorting(
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


def get_resource_changes(
    model_class: type[DeclarativeBase],
    filter_resource_ids: ResourceIdType | list[ResourceIdType] | None = None,
    session: Session | None = None,
    filter_fields: str | list[str] | None = None,
    filter_date_range: tuple[datetime | None, datetime | None] | None = None,
    filter_user_ids: ResourceIdType | list[ResourceIdType] | None = None,
    limit: int | None = None,
    offset: int | None = None,
    sort_by: str | None = "timestamp",
    sort_direction: Literal["asc", "desc"] = "desc",
) -> list[SQLAuditRecord]:
    """
    Retrieve changes for a specific resource model with additional functionalities.

    Args:
        model_class (type[DeclarativeBase]): The SQLAlchemy model class to retrieve changes for.
        session (Session | None): An optional SQLAlchemy session. If None, a new session will be created.
        filter_resource_ids (str | list[str] | None): Resource IDs to filter changes by.
        filter_fields (str | list[str] | None): Specific fields to filter changes by.
        filter_date_range (tuple[datetime | None, datetime | None] | None): Start and end dates for filtering.
        filter_user_ids (ResourceIdType | list[ResourceIdType] | None): User IDs to filter changes by.
        limit (int | None): Maximum number of records to retrieve.
        offset (int | None): Number of records to skip.
        sort_by (str | None): Field to sort the results by.
        sort_direction (Literal["asc", "desc"]): Direction of sorting, either "asc" or "desc".

    Returns:
        list[SQLAuditRecord]: A list of SQLAuditRecord objects representing the changes.
    """
    config = get_config()

    should_close_session = False
    if session is None:
        session = config.session_factory().__next__()
        should_close_session = True

    try:
        logs_users = _logs_users_enabled(config)
        table_model = _get_table_model(model_class)
        audit_log_table = _get_audit_log_table_or_raise(
            session, table_model.__tablename__
        )

        audit_log_fields = _get_filtered_audit_fields(
            session, audit_log_table.table_id, filter_fields
        )

        field_map = _build_field_map(audit_log_fields)

        query = _build_audit_query(
            session=session,
            field_ids=list(field_map.keys()),
            filter_resource_ids=_ensure_valid_resource_ids(filter_resource_ids),
            filter_date_range=filter_date_range,
            filter_user_ids=filter_user_ids,
            logs_users=logs_users,
        )

        query = _apply_sorting(query, sort_by, sort_direction)

        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        res = _build_change_records(
            query.all(), table_model, audit_log_table, field_map
        )

        return res
    finally:
        if should_close_session:
            session.close()
