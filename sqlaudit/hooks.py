import datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from sqlaudit._internals.buffer import AuditChangeBuffer
from sqlaudit.config import get_config
from sqlaudit.context import get_audit_context
from sqlaudit.process import get_changes, register_change
from sqlaudit._internals.registry import audit_model_registry
from sqlaudit._internals.types import LogContextInternal

_audit_change_buffer = AuditChangeBuffer()


def register_hooks():
    """
    Register SQLAlchemy session event listeners to track and store audit logs.

    Hooks:
        - before_flush: Collects audit changes for all tracked instances before data is flushed.
        - after_flush_postexec: Persists buffered audit changes after the flush is executed.
    """

    @event.listens_for(Session, "before_flush")
    def collect_audit_changes_before_flush(session: Session, _, _2):
        """
        Collect pending changes from the session just before the flush occurs.

        This includes `new`, `dirty`, and `deleted` instances that are registered
        in the audit registry. A timestamp and user context are attached to the changes.
        """
        config = get_config()
        timestamp = datetime.datetime.now(datetime.UTC)

        context = get_audit_context()
        if not context.changed_by:
            context.changed_by = (
                str(config.get_user_id_callback())
                if callable(config.get_user_id_callback)
                else None
            )

        for instance in session.dirty | session.new | session.deleted:
            if instance in audit_model_registry:
                _audit_change_buffer.add(
                    instance=instance,
                    changes=get_changes(instance),
                    context=LogContextInternal(
                        **context.__dict__,
                        timestamp=timestamp,
                    ),
                )

    @event.listens_for(Session, "after_flush_postexec")
    def commit_audit_changes_after_flush(session: Session, _):
        """
        Commit the buffered audit changes after the flush is finalized.

        This ensures that the audit log is only written once the database changes are complete.
        """
        for model, changes in _audit_change_buffer:
            register_change(
                session=session,
                entries=changes,
            )
        _audit_change_buffer.clear()


__all__ = ["register_hooks"]
