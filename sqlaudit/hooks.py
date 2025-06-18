import datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from sqlaudit._internals.buffer import AuditChangeBuffer
from sqlaudit._internals.registry import audit_model_registry
from sqlaudit._internals.types import LogContextInternal
from sqlaudit.config import get_config
from sqlaudit.context import AuditContextManager, clear_audit_context, get_audit_context, set_audit_context
from sqlaudit.process import get_changes, register_change

_audit_change_buffer = AuditChangeBuffer()


def register_hooks():
    """
    Register SQLAlchemy session event listeners to track and store audit logs.
    """

    @event.listens_for(Session, "before_flush")
    def collect_audit_changes_before_flush(session: Session, _, _2):
        config = get_config()
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        context = get_audit_context()
        if not context.changed_by and callable(config.get_user_id_callback):
            user_id = config.get_user_id_callback()
            set_audit_context(user_id=str(user_id), reason=context.reason, impersonated_by=context.impersonated_by)
            context = get_audit_context()

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
        for model, changes in _audit_change_buffer:
            register_change(
                session=session,
                entries=changes,
            )
        _audit_change_buffer.clear()
        clear_audit_context()

__all__ = ["register_hooks"]
