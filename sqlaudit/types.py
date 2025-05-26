from dataclasses import dataclass
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import Integer, String, DateTime, UUID
import uuid
import datetime


class SQLAuditBase(DeclarativeBase):
    ...


class AuditLogTable(SQLAuditBase):
    __tablename__ = "AuditLogTables"

    table_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    record_id_field: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=True)


class AuditLogField(SQLAuditBase):
    __tablename__ = "AuditLogFields"

    field_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)


class AuditLog(SQLAuditBase):
    __tablename__ = "AuditLogs"

    audit_log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[int] = mapped_column(Integer, nullable=False)
    record_id: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[str] = mapped_column(String, nullable=True)
    new_value: Mapped[str] = mapped_column(String, nullable=True)
    user_id: Mapped[str] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.utcnow)


@dataclass
class SQLAuditOptions:
    tracked_fields: list[str]
    record_id_field: str
    user_id_field: str
    table_label: str | None = None
