import datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Session

from sqlaudit._internals.buffer import AuditChangeBuffer
from sqlaudit._internals.registry import audit_model_registry
from sqlaudit._internals.types import LogContextInternal
from sqlaudit.config import get_config
from sqlaudit.context import (
    clear_audit_context,
    get_audit_context,
    set_audit_context,
)
from sqlaudit.process import get_changes, register_change

_audit_change_buffer = AuditChangeBuffer()


def register_hooks():
    """
    Register SQLAlchemy session event listeners to track and store audit logs.
    """

    _pending_instances: set[DeclarativeBase] = set()


    @event.listens_for(Session, "before_flush")
    def collect_instances_before_flush(session: Session, _: Any, _2: Any):
        _pending_instances.update(
            instance for instance in session.dirty | session.new | session.deleted
            if instance in audit_model_registry
        )

    @event.listens_for(Session, "after_flush")
    def collect_audit_changes_after_flush(session: Session, _: Any):
        config = get_config()
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        context = get_audit_context()
        if not context.changed_by and callable(config.get_user_id_callback):
            user_id = config.get_user_id_callback()
            set_audit_context(user_id=str(user_id), reason=context.reason, impersonated_by=context.impersonated_by)
            context = get_audit_context()

        for instance in _pending_instances:
            _audit_change_buffer.add(
                instance=instance,
                changes=get_changes(instance),
                context=LogContextInternal(
                    **context.__dict__,
                    timestamp=timestamp,
                ),
            )
        _pending_instances.clear()

    @event.listens_for(Session, "after_flush_postexec")
    def commit_audit_changes_after_flush(session: Session, _: Any):
        for _, changes in _audit_change_buffer:
            register_change(
                session=session,
                entries=changes,
            )
        _audit_change_buffer.clear()
        clear_audit_context()

__all__ = ["register_hooks"]
