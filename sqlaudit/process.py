import json
from typing import Any
from collections.abc import Iterable
import uuid
import warnings

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.orm.session import Session

from sqlaudit.config import get_config
from sqlaudit.models import SQLAuditLogField, SQLAuditLogTable
from sqlaudit.registry import audit_model_registry
from sqlaudit.utils import add_audit_log


class AuditChange(BaseModel):
    """Represents a field change for auditing."""

    field: str
    old_value: list[str]
    new_value: list[str]

    model_config = ConfigDict(
        extra="forbid",
    )


def _get_audit_table(instance: DeclarativeBase, session: Session):
    """
    Retrieves the audit log table for the given instance.
    If it does not exist, it creates a new one.
    """
    metadata = audit_model_registry.get(instance)
    record_id_field = (
        metadata.options.record_id_field
        or metadata.table_model.__mapper__.primary_key[0].name
    )

    log_table_db = (
        session.query(SQLAuditLogTable)
        .filter_by(table_name=metadata.table_model.__tablename__)
        .first()
    )

    if not log_table_db:
        log_table_db = SQLAuditLogTable(
            table_name=metadata.table_model.__tablename__,
            record_id_field=record_id_field,
            label=metadata.options.table_label,
        )
        session.add(log_table_db)

    return log_table_db


def _get_audit_log_field_from_table(
    table: SQLAuditLogTable,
    field: str,
    session: Session,
) -> SQLAuditLogField:
    """
    Retrieves the audit log field for the given instance and field name.
    If it does not exist, it creates a new one.
    """
    for obj in session.new:
        if (
            isinstance(obj, SQLAuditLogField)
            and obj.table_id == table.table_id
            and obj.field_name == field
        ):
            return obj

    # Query the database directly to check if the field exists
    field_db = (
        session.query(SQLAuditLogField)
        .filter_by(table_id=table.table_id, field_name=field)
        .first()
    )

    if field_db:
        return field_db

    field_db = SQLAuditLogField(
        table_id=table.table_id,
        field_name=field,
        table=table,
    )
    session.add(field_db)

    return field_db


def register_change(
    instance: DeclarativeBase, changes: list[AuditChange], session: Session
) -> None:
    """
    Registers the field-level changes of an object into the audit log.
    """
    config = get_config()

    executing_user_id = (
        config.get_user_id_callback() if config.get_user_id_callback else None
    )
    executing_user_id_str = str(executing_user_id) if executing_user_id else None

    metadata = audit_model_registry.get(instance)
    record_id_field = (
        metadata.options.record_id_field
        or metadata.table_model.__mapper__.primary_key[0].name
    )

    record_id = getattr(instance, record_id_field, None)
    if record_id is None:
        raise ValueError(
            "Instance %r does not have a value for the record ID field %r."
            % (instance, record_id_field)
        )

    table_db = _get_audit_table(
        instance=instance,
        session=session,
    )

    for change in changes:
        field_db = _get_audit_log_field_from_table(
            table=table_db,
            field=change.field,
            session=session,
        )

        add_audit_log(
            field=field_db,
            session=session,
            record_id=record_id,
            old_value=change.old_value,
            new_value=change.new_value,
            changed_by=executing_user_id_str,
        )


def _audit_changes_values_encoder(values: Iterable[Any]) -> list[str]:
    """
    Encodes the values for the audit log.
    Converts all values to strings.
    """
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
        raise TypeError(f"Expected an iterable of values, got {type(values).__name__} instead.")

    encoded = []

    for value in values:
        try:
            if isinstance(value, (str, int, float, uuid.UUID)):
                encoded.append(str(value))

            elif isinstance(value, (list, tuple, dict)):
                encoded.append(json.dumps(value, default=str))

            else:
                encoded.append(str(value))

        except Exception as e:
            warnings.warn(
                f"Could not encode value {value!r} of type {type(value).__name__}: {e}",
                category=RuntimeWarning,
            )

    return encoded


def get_changes(instance: DeclarativeBase) -> list[AuditChange]:
    """
    Detects changes to tracked fields of the given object and registers them in the audit log.
    """
    changes: list[AuditChange] = []

    entry = audit_model_registry.get(instance)
    if entry is None:
        warnings.warn(
            f"Model {instance.__class__.__name__} is not registered in SQLAudit registry.",
            category=RuntimeWarning,
        )
        return changes

    tracked_fields = entry.options.tracked_fields

    for field in tracked_fields:
        if not hasattr(instance, field):
            continue

        history = get_history(obj=instance, key=field)

        if not history.has_changes():
            continue

        old_state = list(history.deleted) + list(history.unchanged)
        new_state = list(history.added) + list(history.unchanged)

        if old_state != new_state:
            changes.append(
                AuditChange(
                    field=field,
                    old_value=_audit_changes_values_encoder(old_state),
                    new_value=_audit_changes_values_encoder(new_state),
                )
            )

    return changes
