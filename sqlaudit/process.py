from dataclasses import dataclass

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.orm.session import Session

from sqlaudit.exceptions import SQLAuditInvalidRecordIdFieldError
from sqlaudit.registry import (
    _audit_model_registry,
    _get_audit_log_field,
    get_audit_log_table,
)

from sqlaudit.config import get_audit_config
from sqlaudit.utils import add_audit_log, get_user_id_from_instance


@dataclass
class AuditChange:
    """Represents a field change for auditing."""

    field: str
    old_value: list[str]
    new_value: list[str]


def register_change(
    instance: DeclarativeBase, changes: list[AuditChange], session: Session
) -> None:
    """
    Registers the field-level changes of an object into the audit log.
    """
    config = get_audit_config()
    assert config.session_factory is not None, "Audit session factory is not set"

    metadata = _audit_model_registry.get_metadata(model_class=instance.__class__)
    table_model = metadata.table_model
    options = metadata.options

    audit_log_table = get_audit_log_table(session, table_model.__tablename__)
    table_id = audit_log_table.table_id if audit_log_table else None
    assert table_id is not None, "Audit log table ID is not set"

    record_id = getattr(instance, options.record_id_field, None)
    if not record_id:
        raise SQLAuditInvalidRecordIdFieldError(
            target=instance.__class__, record_id_field=options.record_id_field
        )

    for change in changes:
        field_db = _get_audit_log_field(session, table_id, change.field)
        if not field_db:
            raise SQLAuditInvalidRecordIdFieldError(
                target=instance.__class__, record_id_field=change.field
            )

        add_audit_log(
            session,
            field_id=field_db.field_id,
            record_id=record_id,
            old_value=change.old_value,
            new_value=change.new_value,
            user_id=get_user_id_from_instance(
                instance=instance,
                user_id_field=options.user_id_field,
            ),
        )


def get_changes(instance: DeclarativeBase) -> list[AuditChange]:
    """
    Detects changes to tracked fields of the given object and registers them in the audit log.
    """
    changes: list[AuditChange] = []

    entry = _audit_model_registry.get_table_entry(instance.__class__)

    if entry is None:
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
                AuditChange(field=field, old_value=old_state, new_value=new_state)
            )

    return changes
