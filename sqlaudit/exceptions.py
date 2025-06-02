from sqlalchemy.orm import DeclarativeBase


class SQLAuditConfigError(Exception):
    """Exception raised when the SQLAlchemy audit log config is not set."""

    default_message = (
        "The SQLAlchemy audit log config is not set. "
        "Please call set_audit_config() before using the audit mixin."
    )

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message
        self.name = "SQLAuditConfigError"
        self.description = "The SQLAlchemy audit log config is not set."


class SQLAuditBaseError(Exception):
    """Base exception for SQL audit errors with optional target object support."""

    default_message = "An error occurred with the target '%s'."

    def __init__(
        self,
        message: str | None = None,
        target: type[DeclarativeBase] | None = None,
    ) -> None:
        if target is not None:
            # Get class name if possible (works for class or instance)
            if hasattr(target, "__name__"):  # class
                target_name = target.__name__
            else:  # instance
                target_name = target.__class__.__name__
        else:
            target_name = "object"

        formatted_message = self.default_message % target_name
        final_message = message or formatted_message

        super().__init__(final_message)

        self.message = final_message
        self.target = target
        self.target_name = target_name


class SQLAuditTableNotInDatabaseError(SQLAuditBaseError):
    """Exception raised when the target object is not found in the database."""

    default_message = (
        "The target '%s' is not found in the database. "
        "Please ensure that the object exists in the database. "
        "Is this object registered using the @track_table decorator?"
    )

    description = "The target object is not found in the database."


class SQLAuditUserConfigError(Exception):
    """Exception raised when audit filtering by user_id is used but the user model or column is not configured."""

    default_message = (
        "When filtering by 'user_id', the audit config must have a user model and user_id_column set. "
    )

    description = "The audit config was missing the required user model and user_id_column while filtering by user_id."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.name = "SQLAuditUserConfigError"
        self.description = self.default_message


class SQLAuditTableAlreadyRegisteredError(Exception):
    """Exception raised when a table is already registered for auditing."""

    default_message = "The table '%s' is already registered for auditing."

    def __init__(self, table_name: str, message: str | None = None) -> None:
        super().__init__(message or self.default_message % table_name)
        self.message = message or self.default_message % table_name
        self.table_name = table_name
        self.name = "SQLAuditTableAlreadyRegisteredError"
        self.description = "The table is already registered for auditing."