from datetime import datetime
from typing import Literal

from sqlalchemy.orm import DeclarativeBase, Session

from sqlaudit._internals.utils import (
    apply_sorting,
    build_audit_query,
    build_field_map,
    ensure_valid_resource_ids,
    get_audit_log_table_or_raise,
    get_filtered_audit_fields,
    get_table_model,
    logs_users_enabled,
)
from sqlaudit.config import get_config
from sqlaudit.types import ResourceIdType, SQLAuditRecord


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
        logs_users = logs_users_enabled(config)
        table_model = get_table_model(model_class)

        audit_log_table = get_audit_log_table_or_raise(
            session, table_model.__tablename__
        )

        audit_log_fields = get_filtered_audit_fields(
            session, audit_log_table.table_id, filter_fields
        )

        field_map = build_field_map(audit_log_fields)

        query = build_audit_query(
            session=session,
            field_ids=list(field_map.keys()),
            filter_resource_ids=ensure_valid_resource_ids(filter_resource_ids),
            filter_date_range=filter_date_range,
            filter_user_ids=filter_user_ids,
            logs_users=logs_users,
        )

        query = apply_sorting(query, sort_by, sort_direction)

        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        res = query.all()

        return [SQLAuditRecord.model_validate(audit_log) for audit_log in res]

    finally:
        if should_close_session:
            session.close()
