import datetime
import logging
from typing import Annotated
import uuid
from collections.abc import Callable, Generator

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session as BaseSession

from sqlaudit.exceptions import SQLAuditConfigError
from .models import SQLAuditBase

type SessionFactory = Callable[[], Generator[BaseSession, None, None]]

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class SQLAuditConfig(BaseModel):
    engine: Annotated[
        Engine,
        Field(
            description="SQLAlchemy Engine instance used to connect to the database."
        ),
    ]

    Base: Annotated[
        type[DeclarativeBase],
        Field(description="Declarative base class from which all ORM models inherit."),
    ]

    session_factory: Annotated[
        SessionFactory,
        Field(description="Callable that returns a new SQLAlchemy Session instance."),
    ]

    uuid_factory: Annotated[
        Callable[[], uuid.UUID],
        Field(
            default=uuid.uuid4,
            description="Callable that generates a UUID for new audit entries.",
        ),
    ]

    timestamp_factory: Annotated[
        Callable[[], datetime.datetime],
        Field(
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
            description="Callable that generates a UTC timestamp for audit entries.",
        ),
    ]

    use_autoincrement: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to use auto-incrementing primary keys for audit log entries.",
        ),
    ]

    default_user_id_column: Annotated[
        str | None,
        Field(
            default=None,
            description="Default column name used to identify the user in audited tables (if applicable).",
        ),
    ]

    user_model: Annotated[
        type | None,
        Field(
            default=None,
            description="User model class used to look up user-related audit info. Must be a class, not an instance.",
        ),
    ]

    user_id_column: Annotated[
        str | None,
        Field(
            default=None,
            description="Name of the column on the user model used as a user identifier (e.g. 'id').",
        ),
    ]

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SQLAuditConfigManager:
    def __init__(self) -> None:
        self._config: SQLAuditConfig | None = None

    def set_config(self, config: SQLAuditConfig) -> None:
        if not isinstance(config, SQLAuditConfig):
            raise SQLAuditConfigError("config must be an instance of SQLAuditConfig.")

        # We have to write the metadata from SQLAuditBase to the users metadata
        for table_name, table_obj in SQLAuditBase.metadata.tables.items():
            if table_name not in config.Base.metadata.tables:
                config.Base.metadata._add_table(
                    table_name,
                    table_obj.schema,
                    table_obj,
                )

        self._config = config

    def get_config(self) -> SQLAuditConfig:
        if self._config is None:
            raise SQLAuditConfigError(
                "Please set the audit configuration first using set_audit_config()."
            )
        return self._config

    def __repr__(self) -> str:
        return f"SQLAuditConfigManager(config={self._config})"


_audit_config = SQLAuditConfigManager()


def set_audit_config(
    engine: Engine,
    Base: type[DeclarativeBase],
    session_factory: SessionFactory,
    uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    timestamp_factory: Callable[[], datetime.datetime] = lambda: datetime.datetime.now(
        datetime.timezone.utc
    ),
    use_autoincrement: bool = False,
    default_user_id_field: str | None = None,
    user_model: type | None = None,
    user_id_field: str | None = None,
) -> None:
    """
    This function sets the configuration for SQL audit logging. It is required to be called before any audit operations can be performed.

    Parameters:
        engine (Engine): SQLAlchemy engine instance.
        Base (type[DeclarativeBase]): Base class for SQLAlchemy models, this should be the declarative base class used in your application.
        session_factory (SessionFactory): Factory function for creating sessions.
        uuid_factory (Callable[[], uuid.UUID], optional): Factory for generating UUIDs. Defaults to uuid.uuid4.
        timestamp_factory (Callable[[], datetime.datetime], optional): Factory for generating timestamps. Defaults to UTC now.
        use_autoincrement (bool, optional): Whether to use auto-increment for primary keys. Defaults to False.
        default_user_id_field (str | None, optional): Default user ID field name for audit tables. Defaults to None.
        user_model (type | None, optional): User model class for foreign key relationships. Defaults to None.
        user_id_field (str | None, optional): User ID field name in the user model. Defaults to None.

    Raises:
        SQLAuditConfigError: If any parameter is invalid.
    """
    _audit_config.set_config(
        SQLAuditConfig(
            engine=engine,
            user_model=user_model,
            Base=Base,
            user_id_column=user_id_field,
            uuid_factory=uuid_factory,
            timestamp_factory=timestamp_factory,
            use_autoincrement=use_autoincrement,
            session_factory=session_factory,
            default_user_id_column=default_user_id_field,
        )
    )


def get_audit_config() -> SQLAuditConfig:
    """
    Get the current audit configuration.
    """
    if _audit_config.get_config() is None:
        raise SQLAuditConfigError(
            "Please set the audit configuration first using set_audit_config()."
        )
    return _audit_config.get_config()


def get_audit_base() -> type[DeclarativeBase]:
    """
    Get the base class for audit models.
    """
    try:
        return get_audit_config().Base
    except SQLAuditConfigError:
        raise RuntimeError(
            "Audit logging not configured yet. Please call `set_audit_config()` before importing the audit models."
        )
