from typing import TYPE_CHECKING
import warnings

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.orm.session import Session

from sqlaudit._internals.types import AuditChange
from sqlaudit._internals.models import SQLAuditLogField, SQLAuditLogTable
from sqlaudit._internals.registry import audit_model_registry
from sqlaudit.serializer import Serializer
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
    column = instance.__mapper__.columns.get(field)
    if column is None:
        raise ValueError(f"Column '{field}' does not exist in the instance's mapper.")


    field_db = SQLAuditLogField(
        table_id=table.table_id,
        field_name=field,
        table=table,
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


def get_changes(instance: DeclarativeBase, is_new_instance: bool) -> list[AuditChange]:
    """
    Detects changes to tracked fields of the given object and registers them in the audit log.
    """

    try:
        entry = audit_model_registry.get(instance)

    except KeyError:
        warnings.warn(
            f"Model {instance.__class__.__name__} is not registered in SQLAudit registry.",
            category=RuntimeWarning,
        )
        return []

    changes: list[AuditChange] = []
    for field in entry.options.tracked_fields or entry.trackable_fields:
        if not hasattr(instance, field):
            warnings.warn(
                f"Tracked field {field} does not exist on model {instance.__class__.__name__}.",
                category=RuntimeWarning,
            )
            continue

        history = get_history(obj=instance, key=field)

        # If we have a new instance we can shortcut the history check as all rows are new
        if is_new_instance:
            changes.append(
                AuditChange(
                    field=field,
                    old_value=None,
                    new_value=Serializer.serialize(
                        next(iter(list(history.added) + list(history.unchanged)), None)
                    ),
                )
            )
            continue

        if not history.has_changes():
            continue

        old_state = next(iter(list(history.deleted) + list(history.unchanged)), None)
        new_state = next(iter(list(history.added) + list(history.unchanged)), None)

        if old_state != new_state and (old_state is not None and new_state is not None):
            changes.append(
                AuditChange(
                    field=field,
                    old_value=Serializer.serialize(old_state),
                    new_value=Serializer.serialize(new_state),
                )
            )

    return changes
