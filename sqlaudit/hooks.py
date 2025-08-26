import datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from sqlaudit._internals.buffer import AuditChangeBuffer
from sqlaudit._internals.registry import audit_model_registry
from sqlaudit._internals.types import LogContextInternal
from sqlaudit.config import get_config
from sqlaudit.context import SQLAuditContext, clear_audit_context, get_audit_context, set_audit_context
from sqlaudit.process import get_changes, register_change



def register_hooks():
    """
    Register SQLAlchemy session event listeners to track and store audit logs.
    """

    @event.listens_for(Session, "after_flush")
    def collect_audit_changes_before_flush(session: Session, _,):
        # ensure per-session buffer
        if not hasattr(session, "_audit_change_buffer"):
            setattr(session, "_audit_change_buffer", AuditChangeBuffer())

        config = get_config()
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        context = get_audit_context()
        if not context.changed_by and callable(config.get_user_id_callback):
            user_id = config.get_user_id_callback()
            set_audit_context(
                user_id=str(user_id),
                reason=context.reason,
                impersonated_by=context.impersonated_by,
            )
            context: SQLAuditContext = get_audit_context()

        buffer: AuditChangeBuffer = getattr(session, "_audit_change_buffer")

        # handle new instances (log defaults as new values)
        for instance in session.new:
            if instance in audit_model_registry:
                buffer.add(
                    instance=instance,
                    changes=get_changes(instance, is_new_instance=True),
                    context=LogContextInternal(
                        **context.model_dump(),
                        timestamp=timestamp,
                    ),
                )

        # handle updates/deletes
        for instance in (session.dirty | session.deleted) - session.new:
            if instance in audit_model_registry:
                buffer.add(
                    instance=instance,
                    changes=get_changes(instance, is_new_instance=False),
                    context=LogContextInternal(
                        **context.model_dump(),
                        timestamp=timestamp,
                    ),
                )


    @event.listens_for(Session, "after_flush_postexec")
    def commit_audit_changes_after_flush(session: Session, _):
        buffer: AuditChangeBuffer | None = getattr(session, "_audit_change_buffer", None)
        if not buffer or len(buffer) == 0:
            return
        
        for _, changes in buffer:
            register_change(
                session=session,
                entries=changes,
            )


        buffer.clear()
        clear_audit_context()

__all__ = ["register_hooks"]
