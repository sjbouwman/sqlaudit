from dataclasses import dataclass

from sqlalchemy.orm import DeclarativeBase

from sqlaudit._internals.types import AuditChange, LogContextInternal


@dataclass
class AuditBufferEntry:
    """
    Represents a single entry in the audit change buffer.
    It contains the instance, changes, and an optional context.
    """

    instance: DeclarativeBase
    log_context: LogContextInternal
    changes: list[AuditChange]

    def __post_init__(self):
        assert isinstance(self.instance, DeclarativeBase), (
            "instance must be a subclass of DeclarativeBase, got %s."
            % type(self.instance).__name__
        )
        assert isinstance(self.changes, list), (
            "changes must be a list of AuditChange instances, got %s."
            % type(self.changes).__name__
        )

        assert all(isinstance(change, AuditChange) for change in self.changes), (
            "All items in changes must be instances of AuditChange, got %s."
            % [type(change).__name__ for change in self.changes]
        )


class AuditChangeBuffer:
    """
    A temporary buffer that holds audit changes during a SQLAlchemy session lifecycle.

    This buffer is filled before a flush and consumed after the flush is complete,
    ensuring all audit logs are written in sync with database commits.
    """

    def __init__(self):
        self._audit_change_buffer: dict[
            DeclarativeBase, list[AuditBufferEntry]
        ] = {}


        

    def add(
        self,
        instance: DeclarativeBase,
        changes: list[AuditChange],
        context: LogContextInternal,
    ):
        """
        Add audit changes for a specific ORM instance to the buffer.

        Args:
            instance (DeclarativeBase): The model instance being changed.
            changes (list[AuditChange]): A list of changes detected on the instance.
            context (LogContextInternal): Contextual metadata about the change (e.g., who made it).
        """
        entry = AuditBufferEntry(
            changes=changes, log_context=context, instance=instance
        )
        if instance not in self._audit_change_buffer:
            self._audit_change_buffer[instance] = [entry]

        else:
            self._audit_change_buffer[instance].append(entry)

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

    def __len__(self):
        """
        Return the number of items in the buffer.
        """
        return len(self._audit_change_buffer)

    def __contains__(self, instance: DeclarativeBase):
        """
        Check if the buffer contains changes for a specific instance.
        """
        return instance in self._audit_change_buffer
