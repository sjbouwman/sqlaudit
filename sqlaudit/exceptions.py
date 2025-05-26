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

        # Store attributes for later use or introspection
        self.message = final_message
        self.target = target
        self.target_name = target_name


class SQLAuditTableNotRegistredError(SQLAuditBaseError):
    """Exception raised when the target object is not registered in the audit registry."""

    default_message = (
        "The target '%s' is not registered in the audit registry. "
        "Please ensure that the object is tracked using the @track_table decorator."
    )

    description = "The target object is not registered in the audit registry."


class SQLAuditTableNotInDatabaseError(SQLAuditBaseError):
    """Exception raised when the target object is not found in the database."""

    default_message = (
        "The target '%s' is not found in the database. "
        "Please ensure that the object exists in the database. "
        "Is this object registered using the @track_table decorator?"
    )

    description = "The target object is not found in the database."


class SQLAuditInvalidRecordIdFieldError(SQLAuditBaseError):
    """Exception raised when the record_id_field does not exist in the target object."""

    default_message = (
        "The record_id_field '%s' does not exist in the target '%s'. "
        "Please ensure that the field is defined in the tracked table."
    )

    description = "The record_id_field does not exist in the target object."

    def __init__(self, record_id_field: str, target: type[DeclarativeBase]) -> None:
        message = self.default_message % (record_id_field, target.__name__)
        super().__init__(message, target)


class SQLAuditUserModelNotSetError(SQLAuditBaseError):
    """Exception raised when the user model is not set in the audit config."""

    default_message = (
        "The user model is not set in the audit config. "
        "Please set the user_model parameter in the set_audit_config() function."
    )

    description = "The user model is not set in the audit config."

    def __init__(self) -> None:
        super().__init__(self.default_message)
        self.message = self.default_message
        self.name = "SQLAuditUserModelNotSetError"


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


