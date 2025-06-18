from contextlib import AbstractContextManager
from contextvars import ContextVar, Token
from typing import Annotated
from pydantic import BaseModel, Field

from .config import get_config

from .types import ResourceIdType


class SQLAuditContext(BaseModel):
    changed_by: Annotated[
        str | None,
        Field(
            description="The identifier of the user performing the change. If not provided it will use the `get_user_id_callback` from the SQLAuditConfig.",
            max_length=256,
            min_length=1,
        ),
    ] = None

    reason: Annotated[
        str | None,
        Field(
            description="A brief description of the reason for the change. This is optional and can be used to provide context for the audit entry.",
            max_length=512,
            min_length=1,
        ),
    ] = None

    impersonated_by: Annotated[
        str | None,
        Field(
            description="The identifier of the user who is impersonating another user. This is useful for tracking changes made by users on behalf of others.",
            max_length=256,
            min_length=1,
        ),
    ] = None


_sql_audit_context: ContextVar[SQLAuditContext] = ContextVar(
    "sql_audit_context", default=SQLAuditContext()
)


def set_audit_context(
    *,
    user_id: str | None = None,
    reason: str | None = None,
    impersonated_by: str | None = None,
) -> SQLAuditContext:
    """
    Update the current SQLAuditContext with new values. Will set a new state for the context variable.

    Args:
        user_id (str | None): The identifier of the user performing the change. If not provided, it will use the `get_user_id_callback` from the SQLAuditConfig.
        reason (str | None): A brief description of the reason for the change. This is optional and can be used to provide context for the audit entry.
        impersonated_by (str | None):  The identifier of the user who is impersonating another user. This is useful for tracking changes made by users on behalf of others.
    """
    _sql_audit_context.set(
        SQLAuditContext(
            changed_by=user_id, reason=reason, impersonated_by=impersonated_by
        )
    )

    return _sql_audit_context.get()


def clear_audit_context() -> None:
    """
    Clear the current SQLAuditContext, resetting it to its default state.
    """
    set_audit_context()


def get_audit_context() -> SQLAuditContext:
    """
    Retrieve the current SQLAuditContext.

    Returns:
        SQLAuditContext: The current audit context.
    """
    return _sql_audit_context.get()


class AuditContextManager(AbstractContextManager):
    """
    A context manager for managing the SQLAuditContext.
    Allows setting a new context for the duration of the context block, and automatically resets it afterwards.

    Usage:
    with AuditContextManager(user_id="123", reason="Update record") as context:
        # Perform operations that should be audited
        ....

        db.flush()  # Ensure changes are committed so the hook can capture them

    After exiting the context, the SQLAuditContext will be reset to its previous state.
    """

    def __init__(
        self,
        *,
        user_id: ResourceIdType | None = None,
        reason: str | None = None,
        impersonated_by: ResourceIdType | None = None,
    ):
        config = get_config()

        if not user_id and callable(config.get_user_id_callback):
            user_id = config.get_user_id_callback()

        self.new_context = SQLAuditContext(
            changed_by=str(user_id) if user_id else None,
            reason=reason,
            impersonated_by=str(impersonated_by),
        )

        self.token: Token | None = None

    def __enter__(self) -> SQLAuditContext:
        self.token = _sql_audit_context.set(self.new_context)
        return self.new_context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.token is not None:
            _sql_audit_context.reset(self.token)


__all__ = [
    "set_audit_context",
    "clear_audit_context",
    "get_audit_context",
    "AuditContextManager",
    "SQLAuditContext",
]
