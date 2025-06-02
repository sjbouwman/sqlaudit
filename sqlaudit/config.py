import uuid
from tzlocal import get_localzone

from collections.abc import Callable, Generator
from dataclasses import dataclass
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session as BaseSession, DeclarativeBase

from sqlaudit.exceptions import SQLAuditConfigError
from sqlaudit.models import SQLAuditBase

type _SessionFactory = Callable[[], Generator[BaseSession, None, None]]


@dataclass
class SQLAuditConfig:
    session_factory: _SessionFactory
    user_model: type | None = None
    user_model_user_id_field: str | None = None
    get_user_id_callback: Callable[[], str | int | uuid.UUID | None] | None = None
    time_zone: str | None = None

    _user_tz: ZoneInfo | None = None

    def __post_init__(self):
        if not callable(self.session_factory):
            raise SQLAuditConfigError(
                "session_factory must be a callable that returns a Session generator."
            )

        try:
            test_gen = self.session_factory()
            if not isinstance(test_gen, Generator):
                raise TypeError

        except Exception:
            raise SQLAuditConfigError(
                "session_factory must return a Generator yielding SQLAlchemy Session objects."
            )

        if self.user_model is not None:
            if not issubclass(self.user_model, DeclarativeBase):
                raise SQLAuditConfigError(
                    "user_model must be a class (DeclarativeBase) or None."
                )

            if not callable(self.get_user_id_callback):
                raise SQLAuditConfigError(
                    "get_user_id_callback must be a callable when user_model is set."
                )

            if not isinstance(self.user_model_user_id_field, str):
                raise SQLAuditConfigError(
                    "user_model_user_id_field must be a string if user_model is set. Received: %s"
                    % type(self.user_model_user_id_field).__name__
                )

            if not hasattr(self.user_model, self.user_model_user_id_field):
                raise SQLAuditConfigError(
                    "user_model (%s) does not have a field named '%s', which is set as 'user_model_user_id_field'."
                    % (self.user_model.__name__, self.user_model_user_id_field)
                )

        if self.time_zone is not None and not isinstance(self.time_zone, str):
            raise SQLAuditConfigError(
                "time_zone must be a string or None. Received: %s"
                % type(self.time_zone).__name__
            )

        if self.time_zone is not None:
            try:
                self._user_tz = ZoneInfo(self.time_zone)
            except Exception as e:
                raise SQLAuditConfigError(
                    f"Invalid time zone: {self.time_zone}. Error: {e}"
                )
        else:
            self._user_tz = get_localzone()


class SQLAuditConfigManager:
    def __init__(self) -> None:
        self._config: SQLAuditConfig | None = None

    def set_config(self, config: SQLAuditConfig) -> None:
        if not isinstance(config, SQLAuditConfig):
            raise SQLAuditConfigError("config must be an instance of SQLAuditConfig.")

        # No other validation has to be done here, as SQLAuditConfig already validates itself.

        SQLAuditBase.metadata.create_all(
            bind=config.session_factory().__next__().get_bind()
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


def has_config() -> bool:
    """
    Check if the SQLAudit configuration has been set.
    Returns:
        bool: True if the configuration is set, False otherwise.
    """
    return _audit_config._config is not None


def set_config(config: SQLAuditConfig) -> None:
    _audit_config.set_config(config=config)


def get_config() -> SQLAuditConfig:
    """
    Get the current SQLAudit configuration.

    Raises:
        SQLAuditConfigError: If the configuration has not been set.
    """
    return _audit_config.get_config()


def clear_config() -> None:
    """
    Clear the current SQLAudit configuration.
    """
    _audit_config._config = None


__all__ = [
    "SQLAuditConfig",
    "set_config",
    "get_config",
    "has_config",
]
