from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase, Session

from sqlaudit.config import get_audit_config
from sqlaudit.registry import _audit_model_registry


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
    instance: DeclarativeBase, user_id_field: str | None
) -> str | None:
    """
    Extracts the user ID from the given object based on the specified user ID field.
    If the field is not set, returns None.
    """
    if user_id_field is None or not hasattr(instance, user_id_field):
        return None

    user_id = getattr(instance, user_id_field, None)
    if user_id is None:
        return None

    return str(user_id) if isinstance(user_id, (str, int)) else None


def add_audit_log(
    session: Session,
    field_id: int,
    record_id: str,
    old_value: list[str],
    new_value: list[str],
    user_id: str | None = None,
):
    """
    Adds an audit log entry to the database. 
    """
    config = get_audit_config()
    audit_log_db = _audit_model_registry.base_models.AuditLog(
        field_id=field_id,
        record_id=record_id,
        old_value=old_value,
        new_value=new_value,
    )

    if user_id is not None and config.user_id_column and config.user_model:
        audit_log_db.user_id = user_id

    session.add(audit_log_db)
    return audit_log_db


def table_exists(session: Session, table_name: str) -> bool:
    """
    Checks if a table exists in the database.
    """
    inspector = inspect(session.get_bind())
    return table_name in inspector.get_table_names()
