import datetime
import uuid

from sqlalchemy import JSON, UUID, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# A custom base class for SQLAlchemy models used in the audit system. After setting up the config, the tables will be automatically inserted into the metdata of the 'users' base class.
class SQLAuditBase(DeclarativeBase): ...


class AuditLogTable(SQLAuditBase):
    __tablename__ = "SQLAuditLogTables"
    table_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    record_id_field: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=True)


class AuditLogField(SQLAuditBase):
    __tablename__ = "SQLAuditLogFields"

    field_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)


class AuditLog(SQLAuditBase):
    __tablename__ = "SQLAuditLogs"

    audit_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    field_id: Mapped[int] = mapped_column(Integer, nullable=False)
    record_id: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[JSON] = mapped_column(JSON, nullable=True)
    new_value: Mapped[JSON] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    user_id: Mapped[str] = mapped_column(String, nullable=True)
