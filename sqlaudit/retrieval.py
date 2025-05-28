import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import DeclarativeBase, Session

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

    return [
        str(v) for v in value if v is not None and v != ""
    ]


def _build_field_map(
    fields: list[SQLAuditLogField],
) -> dict[str, SQLAuditLogField]:
    return {str(field.field_id): field for field in fields}


def _get_audit_log_table_or_raise(session: Session, table_name: str):
    audit_log_table = _get_audit_log_table(session, table_name)
    if audit_log_table is None:
        raise SQLAuditTableNotInDatabaseError()
    return audit_log_table


def _build_audit_query(
    session: Session,
    field_lookup: dict[str, SQLAuditLogField],
    filter_resource_ids: list[str],
    filter_date_range: tuple[datetime | None, datetime | None] | None,
    filter_user_ids: ResourceIdType | list[ResourceIdType] | None,
    logs_users: bool,
):
    query = session.query(SQLAuditLog).filter(
        SQLAuditLog.field_id.in_(field_lookup.keys()),
        SQLAuditLog.record_id.in_(filter_resource_ids),
    )

    if filter_date_range:
        start_date, end_date = filter_date_range
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

    return query.order_by(SQLAuditLog.timestamp.desc())


def _build_change_records(
    audit_logs: list[SQLAuditLog],
    table_model: type[DeclarativeBase],
    audit_log_table: SQLAuditLogTable,
    field_lookup: dict[str, SQLAuditLogField],
) -> list[SQLAuditRecord]:
    def ensure_list_str(value: Any) -> list[str]:
        return [str(v) for v in value] if isinstance(value, list) else []

    config = get_config()
    user_id = config.get_user_id_callback() if config.get_user_id_callback else None

    return [
        SQLAuditRecord(
            table_name=table_model.__tablename__,
            resource_id=audit_log.record_id,
            field_name=field_lookup[str(audit_log.field_id)].field_name,
            old_value=ensure_list_str(audit_log.old_value),
            new_value=ensure_list_str(audit_log.new_value),
            timestamp=audit_log.timestamp,
            changed_by=str(user_id) if user_id else None,
            table_label=audit_log_table.label or None,
        )
        for audit_log in audit_logs
    ]


def get_resource_changes(
    model_class: type[DeclarativeBase],
    session: Session,
    filter_resource_ids: ResourceIdType | list[ResourceIdType],
    filter_fields: str | list[str] | None = None,
    filter_date_range: tuple[datetime | None, datetime | None] | None = None,
    filter_user_ids: ResourceIdType | list[ResourceIdType] | None = None,
) -> list[SQLAuditRecord]:
    """
    Retrieve changes for a specific resource model.

    Args:
        model_class (type[DeclarativeBase]): The SQLAlchemy model class to retrieve
            changes for.
        session (Session): The SQLAlchemy session to use for the query.
        filter_resource_ids (str | list[str]): The resource IDs to filter changes by.
        filter_fields (str | list[str] | None): Specific fields to filter changes by.
            If None, all fields are included.
        filter_date_range (tuple[datetime | None, datetime | None] | None): A tuple
            containing start and end dates to filter changes by. If None, no date
            filtering is applied.
        filter_user_ids (ResourceIdType | list[ResourceIdType] | None): User IDs to filter
            changes by. If None, no user filtering is applied.
    Returns:
        list[SQLAuditRecord]: A list of SQLAuditRecord objects representing the changes.
    """

    config = get_config()
    logs_users = _logs_users_enabled(config)

    table_model = _get_table_model(model_class)
    audit_log_table = _get_audit_log_table_or_raise(session, table_model.__tablename__)

    audit_log_fields = _get_filtered_audit_fields(
        session, audit_log_table.table_id, filter_fields
    )
    field_map = _build_field_map(audit_log_fields)
    filter_resource_ids_filtered = _ensure_valid_resource_ids(filter_resource_ids)
    query = _build_audit_query(
        session,
        field_map,
        filter_resource_ids_filtered,
        filter_date_range,
        filter_user_ids,
        logs_users,
    )

    return _build_change_records(query.all(), table_model, audit_log_table, field_map)
