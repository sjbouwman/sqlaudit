import logging

from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Session

from sqlaudit.process import AuditChange, get_changes, register_change
from sqlaudit.registry import _audit_model_registry

logger = logging.getLogger(__name__)


class AuditChangeBuffer:
    """
    A buffer to hold pending audit changes before they are committed to the database.
    This is used to collect changes during the session lifecycle and process them after the flush.
    """

    def __init__(self):
        self._audit_change_buffer: dict[DeclarativeBase, list[AuditChange]] = {}

    def add(self, instance: DeclarativeBase, changes: list[AuditChange]):
        """
        Add changes for a specific instance to the buffer.
        """
        if instance not in self._audit_change_buffer:
            self._audit_change_buffer[instance] = []
        self._audit_change_buffer[instance].extend(changes)
    
    def clear(self):
        """
        Clear the buffer.
        """
        self._audit_change_buffer.clear()

    def items(self):
        """
        Return the items in the buffer.
        """
        return self._audit_change_buffer.items()
    
    def __iter__(self):
        """
        Iterate over the items in the buffer.
        """
        return iter(self._audit_change_buffer.items())


_audit_change_buffer = AuditChangeBuffer()


def register_audit_hooks(session: Session):
    @event.listens_for(session, "before_flush")
    def collect_audit_changes_before_flush(session: Session, _, _2):
        """
        Set the pending audit logs for the session before flushing. Thus will register all changes. These changes will be processed after the flush.
        """
        for instance in session.dirty | session.new | session.deleted:
            if instance in _audit_model_registry:
                _audit_change_buffer.add(
                    instance=instance,
                    changes=get_changes(instance),
                )

    @event.listens_for(session, "after_flush")
    def commit_audit_changes_after_flush(session: Session, _):
        """
        Process the pending audit logs after the session has been flushed.
        This will register the changes in the audit log.
        """
        for instance, changes in _audit_change_buffer:
            register_change(
                session=session,
                instance=instance,
                changes=changes,
            )
        _audit_change_buffer.clear()
