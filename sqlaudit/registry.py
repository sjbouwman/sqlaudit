from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import DeclarativeBase, Session

from sqlaudit.config import get_audit_config
from sqlaudit.logger import logger
from sqlaudit.models import (
    AuditLog,
    AuditLogField,
    AuditLogTable,
)
from sqlaudit.options import SQLAuditOptions

from .exceptions import (
    SQLAuditTableNotInDatabaseError,
    SQLAuditTableNotRegistredError,
    SQLAuditUserConfigError,
)


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

    record_id: Annotated[str, Field(description="Primary key of the affected record")]

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

    user_id: Annotated[
        str | None,
        Field(
            default=None, description="ID of the user who made the change (optional)"
        ),
    ]


def get_audit_log_table(session: Session, table_name: str):
    """
    Get the audit log table for a given table name.
    """
    return (
        session.query(_audit_model_registry.base_models.AuditLogTable)
        .filter_by(table_name=table_name)
        .first()
    )


def add_audit_log_table(
    session: Session, table_name: str, record_id_field: str, label: str | None = None
):
    """
    Add a new audit log table entry.
    """
    audit_log_table_db = _audit_model_registry.base_models.AuditLogTable(
        table_name=table_name,
        record_id_field=record_id_field,
        label=label,
    )
    session.add(audit_log_table_db)
    return audit_log_table_db


def _get_audit_log_field(session: Session, table_id: int, field_name: str | None):
    """
    Get the audit log field for a given table ID and field name.
    """
    return (
        session.query(_audit_model_registry.base_models.AuditLogField)
        .filter_by(table_id=table_id, field_name=field_name)
        .first()
    )


def _get_audit_log_fields_by_table_id(session: Session, table_id: int):
    """
    Get all audit log fields for a given table ID.
    """
    return (
        session.query(_audit_model_registry.base_models.AuditLogField)
        .filter_by(table_id=table_id)
        .all()
    )


def _add_audit_log_field(session: Session, table_id: int, field_name: str):
    """
    Add a new audit log field entry.
    """
    audit_log_field_db = _audit_model_registry.base_models.AuditLogField(
        table_id=table_id,
        field_name=field_name,
    )
    session.add(audit_log_field_db)
    return audit_log_field_db


def _logs_users_enabled(config) -> bool:
    return config.user_model is not None and config.user_id_column is not None


def _get_table_model(model_class: type[DeclarativeBase]):
    sqlaudit_metadata = _audit_model_registry.get_metadata(model_class=model_class)
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


def _ensure_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else value


def _build_field_map(fields: list[AuditLogField]) -> dict[str, AuditLogField]:
    return {str(field.field_id): field for field in fields}


def _get_audit_log_table_or_raise(session: Session, table_name: str):
    audit_log_table = get_audit_log_table(session, table_name)
    if audit_log_table is None:
        raise SQLAuditTableNotInDatabaseError()
    return audit_log_table


def _build_audit_query(
    session: Session,
    field_lookup: dict[str, AuditLogField],
    filter_resource_ids: list[str],
    filter_date_range: tuple[datetime | None, datetime | None] | None,
    filter_user_ids: str | list[str] | None,
    logs_users: bool,
):
    AuditLog = _audit_model_registry.base_models.AuditLog

    query = session.query(AuditLog).filter(
        AuditLog.field_id.in_(field_lookup.keys()),
        AuditLog.record_id.in_(filter_resource_ids),
    )

    if filter_date_range:
        start_date, end_date = filter_date_range
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

    if filter_user_ids is not None:
        if not logs_users:
            raise SQLAuditUserConfigError()
        if isinstance(filter_user_ids, str):
            filter_user_ids = [filter_user_ids]
        query = query.filter(AuditLog.user_id.in_(filter_user_ids))

    return query.order_by(AuditLog.timestamp.desc())


def _build_change_records(
    audit_logs: list[AuditLog],
    table_model: type[DeclarativeBase],
    audit_log_table: AuditLogTable,
    field_lookup: dict[str, AuditLogField],
) -> list[SQLAuditRecord]:
    def ensure_list_str(value: Any) -> list[str]:
        return [str(v) for v in value] if isinstance(value, list) else []

    return [
        SQLAuditRecord(
            table_name=table_model.__tablename__,
            record_id=audit_log.record_id,
            field_name=field_lookup[str(audit_log.field_id)].field_name,
            old_value=ensure_list_str(audit_log.old_value),
            new_value=ensure_list_str(audit_log.new_value),
            timestamp=audit_log.timestamp,
            user_id=audit_log.user_id,
            table_label=audit_log_table.label or None,
        )
        for audit_log in audit_logs
    ]


def get_resource_changes(
    model_class: type[DeclarativeBase],
    session: Session,
    filter_resource_ids: str | list[str],
    filter_fields: str | list[str] | None = None,
    filter_date_range: tuple[datetime | None, datetime | None] | None = None,
    filter_user_ids: str | list[str] | None = None,
) -> list[SQLAuditRecord]:
    config = get_audit_config()
    logs_users = _logs_users_enabled(config)

    table_model = _get_table_model(model_class)
    audit_log_table = _get_audit_log_table_or_raise(session, table_model.__tablename__)
    audit_log_fields = _get_filtered_audit_fields(
        session, audit_log_table.table_id, filter_fields
    )

    field_map = _build_field_map(audit_log_fields)
    filter_resource_ids = _ensure_list(filter_resource_ids)

    query = _build_audit_query(
        session,
        field_map,
        filter_resource_ids,
        filter_date_range,
        filter_user_ids,
        logs_users,
    )
    return _build_change_records(query.all(), table_model, audit_log_table, field_map)


@dataclass
class AuditTableEntry:
    table_model: type[DeclarativeBase]
    options: SQLAuditOptions


@dataclass
class SqlAuditBaseModels:
    AuditLogTable: type[AuditLogTable]
    AuditLogField: type[AuditLogField]
    AuditLog: type[AuditLog]


class AuditRegistry:
    def __init__(self):
        self._registry: dict[str, AuditTableEntry] = {}
        self._base_models: SqlAuditBaseModels | None = None

    def register(self, table_model: type[DeclarativeBase], options: SQLAuditOptions):
        """
        Register a table model and its options for auditing.
        """
        table_name = table_model.__tablename__
        if table_name in self._registry:
            raise ValueError(f"Table {table_name} is already registered for auditing.")

        logger.debug(
            f"Registering table '{table_name}' for auditing with options: {options}"
        )
        self._registry[table_name] = AuditTableEntry(table_model, options)

        # We also have to that the table is added to the database
        config = get_audit_config()

        with next(config.session_factory()) as session:
            assert self.base_models_exist(), (
                "Base models for audit tables are not registered."
            )

            # We first have to make sure the audit log table exists
            assert session is not None, "Session is not available for auditing."

            audit_table_db = get_audit_log_table(session, table_name)
            if audit_table_db is None:
                audit_table_db = add_audit_log_table(
                    session,
                    table_name=table_name,
                    record_id_field=options.record_id_field,
                    label=options.table_label,
                )

            session.flush()  # Ensure the table is committed to the database

            table_id = getattr(audit_table_db, "table_id", None)

            assert table_id is not None, (
                f"Audit log table {table_name} does not have a valid ID."
            )

            for field in options.tracked_fields:
                field_db = _get_audit_log_field(
                    session, table_id=table_id, field_name=field
                )

                if field_db is None:
                    field_db = _add_audit_log_field(
                        field_name=field,
                        table_id=table_id,
                        session=session,
                    )

            session.commit()  # Commit the changes to the database

    def get_metadata(self, model_class: type[DeclarativeBase]) -> AuditTableEntry:
        """
        Get the metadata for a given table model.
        """

        table_name = model_class.__tablename__
        table = self._registry.get(table_name, None)
        if table is None:
            raise SQLAuditTableNotRegistredError(target=model_class)

        return table

    def get_table_entry(
        self, model_class: type[DeclarativeBase]
    ) -> AuditTableEntry | None:
        """
        Get the metadata for a given table model.
        """
        table_name = model_class.__tablename__
        return self._registry.get(table_name, None)

    def clear(self):
        """
        Clear the registry.
        """
        self._registry.clear()

    def __contains__(self, model_class: type[DeclarativeBase]) -> bool:
        """
        Check if a table model is registered for auditing.
        """
        return model_class.__tablename__ in self._registry

    def register_base_models(self, base_models: SqlAuditBaseModels):
        """
        Register the base models for the audit tables.
        """
        self._base_models = base_models

    @property
    def base_models(self) -> SqlAuditBaseModels:
        """
        Get the base models for the audit tables.
        """
        if self._base_models is None:
            raise ValueError("Base models have not been registered.")

        return self._base_models

    def base_models_exist(self) -> bool:
        """
        Check if the base models for the audit tables are registered.
        """
        return self._base_models is not None


_audit_model_registry = AuditRegistry()
