import json
from typing import TYPE_CHECKING, Any
import uuid
import warnings

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.orm.session import Session

from sqlaudit._internals.types import AuditChange
from sqlaudit.exceptions import SQLAuditUnsupportedDataTypeError
from sqlaudit._internals.models import SQLAuditLogField, SQLAuditLogTable
from sqlaudit._internals.registry import audit_model_registry
from sqlaudit.types import _allowed_dtypes
from sqlaudit._internals.utils import add_audit_change, add_audit_log

if TYPE_CHECKING:
    from sqlaudit._internals.buffer import AuditBufferEntry


def _get_audit_table(instance: DeclarativeBase, session: Session):
    """
    Retrieves the audit log table for the given instance.
    If it does not exist, it creates a new one.
    """
    metadata = audit_model_registry.get(instance)
    resource_id_field = (
        metadata.options.resource_id_field
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
            resource_id_field=resource_id_field,
            label=metadata.options.table_label,
        )
        session.add(log_table_db)

    return log_table_db


def _get_audit_log_field_from_table(
    table: SQLAuditLogTable,
    field: str,
    session: Session,
    instance: DeclarativeBase,
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

    # We need to create a new field entry
    dtype = instance.__mapper__.columns[field].type.python_type.__name__
    if dtype not in list(_allowed_dtypes.keys()):
        raise SQLAuditUnsupportedDataTypeError(
            "Data type '%s' for field '%s' is not supported for auditing. Available types: %s"
            % (dtype, field, ", ".join(_allowed_dtypes.keys()))
        )

    field_db = SQLAuditLogField(
        table_id=table.table_id,
        field_name=field,
        table=table,
        dtype=instance.__mapper__.columns[field].type.python_type.__name__,
    )
    session.add(field_db)

    return field_db


def _register_entry_changes(
    entry: "AuditBufferEntry",
    table_db: SQLAuditLogTable,
    session: Session,
) -> None:
    """
    Registers the changes of a single entry in the audit log.
    This function is called for each entry in the audit change buffer.
    """

    if not entry.changes:
        return

    metadata = audit_model_registry.get(entry.instance)
    resource_id_field = (
        metadata.options.resource_id_field
        or metadata.table_model.__mapper__.primary_key[0].name
    )

    resource_id: str | None = str(getattr(entry.instance, resource_id_field, None))
    if resource_id is None:
        raise ValueError(
            f"Instance {entry.instance} does not have a value for the record ID field {resource_id_field}."
        )

    log_db = add_audit_log(
        table=table_db,
        resource_id=resource_id,
        context=entry.log_context,
        session=session,
    )

    for change in entry.changes:
        field_db = _get_audit_log_field_from_table(
            table=table_db,
            field=change.field,
            instance=entry.instance,
            session=session,
        )

        add_audit_change(
            field=field_db,
            log=log_db,
            change=change,
            session=session,
        )


def register_change(
    entries: list["AuditBufferEntry"],
    session: Session,
) -> None:
    """
    Registers the field-level changes of an object into the audit log.
    """

    if len(entries) == 0:
        return

    table_db: SQLAuditLogTable = _get_audit_table(
        instance=entries[0].instance,
        session=session,
    )

    for entry in entries:
        _register_entry_changes(
            entry=entry,
            session=session,
            table_db=table_db,
        )


def _audit_changes_values_encoder(value: Any) -> str | None:
    """
    An encoder for values in audit changes.
    It converts various data types to a string representation, as this is the type we use in DB.
    """
    if value is None:
        return None

    try:
        if isinstance(value, (str, int, float, uuid.UUID)):
            return str(value)

        elif isinstance(value, (list, tuple, dict)):
            return json.dumps(value, default=str)

        else:
            return str(value)

    except Exception as e:
        warnings.warn(
            f"Could not encode value {value!r} of type {type(value).__name__}: {e}",
            category=RuntimeWarning,
        )

        return None


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

    tracked_fields = entry.options.tracked_fields or entry.trackable_fields

    for field in tracked_fields:
        if not hasattr(instance, field):
            continue

        history = get_history(obj=instance, key=field)

        if not history.has_changes():
            continue

        old_state_list = list(history.deleted) + list(history.unchanged)
        new_state_list = list(history.added) + list(history.unchanged)

        # We convert the lists to single values or None if they are empty
        old_state = old_state_list[0] if old_state_list else None
        new_state = new_state_list[0] if new_state_list else None

        if old_state != new_state:
            changes.append(
                AuditChange(
                    field=field,
                    old_value=_audit_changes_values_encoder(old_state),
                    new_value=_audit_changes_values_encoder(new_state),
                )
            )

    return changes
