from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class LogContextInternal:
    """
    Context for SQL Audit logging.
    This can be extended to include additional metadata as needed.
    """

    timestamp: datetime
    changed_by: str | None = None
    impersonated_by: str | None = None
    reason: str | None = None

    def __post_init__(self):
        assert isinstance(self.timestamp, datetime), (
            "timestamp must be a datetime.datetime instance, got %s."
            % type(self.timestamp).__name__
        )

        if self.changed_by is not None:
            assert isinstance(self.changed_by, str), (
                "changed_by must be a str or None, got %s."
                % type(self.changed_by).__name__
            )

        if self.impersonated_by is not None:
            assert isinstance(self.impersonated_by, str), (
                "impersonated_by must be a str or None, got %s."
                % type(self.impersonated_by).__name__
            )

        if self.reason is not None:
            assert isinstance(self.reason, str), (
                "reason must be a str or None, got %s." % type(self.reason).__name__
            )

    def dump(self) -> dict[str, Any]:
        """
        Dump the context to a dictionary for logging.
        """
        return {
            "timestamp": self.timestamp,
            "changed_by": self.changed_by,
            "impersonated_by": self.impersonated_by,
            "reason": self.reason,
        }


@dataclass
class AuditChange:
    """Represents a field change for auditing."""

    field: str
    old_value: str | None
    new_value: str | None