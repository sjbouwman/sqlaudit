import logging

from sqlalchemy.orm import DeclarativeBase

from sqlaudit.options import SQLAuditOptionsBase, convert_base_to_sql_audit_options
from sqlaudit.config import get_audit_base, get_audit_config

from sqlaudit.models import (
    AuditLog,
    AuditLogField,
    AuditLogTable,
)
from sqlaudit.registry import SqlAuditBaseModels, _audit_model_registry
from sqlaudit.utils import get_primary_keys, table_exists

logger = logging.getLogger(__name__)


def run_preflight(table: type[DeclarativeBase], options: SQLAuditOptionsBase) -> None:
    """Initializes audit configuration for a SQLAlchemy table.

    - Registers base audit models if not present.
    - Ensures required audit tables exist in the database.
    - Registers the provided table for auditing.
    """

    if _audit_model_registry.base_models_exist() and table in _audit_model_registry:
        return # End early if the table is already registered

    if not options.record_id_field:
        primary_keys = get_primary_keys(table)

        options.record_id_field = primary_keys[0]

        logger.warning(
            "No 'record_id_field' provided for '%s'. Using primary key '%s' as default.",
            table.__name__,
            options.record_id_field,
        )

    # Register base models and ensure audit tables exist
    if not _audit_model_registry.base_models_exist():
        Base = get_audit_base()


        audit_config = get_audit_config()
        with next(audit_config.session_factory()) as session:
            if not table_exists(session, AuditLogTable.__tablename__):
                Base.metadata.create_all(session.get_bind())

        _audit_model_registry.register_base_models(
            SqlAuditBaseModels(
                AuditLogTable=AuditLogTable,
                AuditLogField=AuditLogField,
                AuditLog=AuditLog,
            )
        )

    # Register the provided table for auditing
    if table not in _audit_model_registry:
        _audit_model_registry.register(
            table_model=table, options=convert_base_to_sql_audit_options(options)
        )
