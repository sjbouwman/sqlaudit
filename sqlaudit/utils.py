from typing import cast

from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql.schema import ForeignKey

from sqlaudit.config import get_config
from sqlaudit.models import SQLAuditLog, SQLAuditLogField


def column_is_foreign_key_of(
    table: type[DeclarativeBase],
    column_name: str,
    foreign_table_name: str,
    foreign_column_name: str,
) -> bool:
    """
    Check if the specified column in the table has a foreign key constraint.

    Args:
        table (type[DeclarativeBase]): The SQLAlchemy table model.
        column_name (str): The name of the column to check.

    Returns:
        bool: True if the column has a foreign key, False otherwise.
    """
    column = getattr(table, column_name)

    foreign_keys: tuple[ForeignKey] = cast(
        tuple[ForeignKey], getattr(column, "foreign_keys", ())
    )

    if not foreign_keys:
        return False

    for fk in foreign_keys:
        if fk.target_fullname == f"{foreign_table_name}.{foreign_column_name}":
            return True

    return False


def get_primary_keys(table: type[DeclarativeBase]) -> list[str]:
    """
    Retrieves the primary key fields of a SQLAlchemy table.

    Args:
        table (type[DeclarativeBase]): The SQLAlchemy table class.

    Returns:
        list[str]: A list of primary key field names.
    """
    primary_keys = inspect(table).primary_key
    if not primary_keys:
        raise ValueError(f"Table {table.__name__} has no primary key defined.")

    return [pk.name for pk in primary_keys]


def get_user_id_from_instance(
    instance: DeclarativeBase, user_id_field: str
) -> str | None:
    """
    Extracts the user ID from the given object based on the specified user ID field.
    If the field is not set, returns None.
    """
    if user_id_field is None or not hasattr(instance, user_id_field):
        raise ValueError(f"Instance does not have the user_id field '{user_id_field}'.")

    user_id = getattr(instance, user_id_field, None)
    if user_id is None:
        return None

    return str(user_id) if isinstance(user_id, (str, int)) else None


def add_audit_log(
    session: Session,
    field: SQLAuditLogField,
    record_id: str,
    old_value: list[str],
    new_value: list[str],
    changed_by: str | None = None,
):
    """
    Adds an audit log entry to the database.
    """
    config = get_config()

    audit_log_db = SQLAuditLog(
        field=field,
        record_id=record_id,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by,
    )

    if changed_by is not None:
        if not config.user_model:
            raise ValueError(
                "User model is not set in the audit configuration whilest user_id is provided."
            )

        # We get the column name for the user ID in the audit log
        audit_log_user_id_column = (
            config.user_model_user_id_field or get_primary_keys(config.user_model)[0]
        )

        setattr(audit_log_db, audit_log_user_id_column, changed_by)

    session.add(audit_log_db)
    return audit_log_db


def table_exists(session: Session, table_name: str) -> bool:
    """
    Checks if a table exists in the database.
    """
    inspector = inspect(session.get_bind())
    return table_name in inspector.get_table_names()
