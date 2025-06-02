import datetime
import uuid

from sqlalchemy import JSON, TIMESTAMP, ForeignKey, String
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class SQLAuditBase(DeclarativeBase): ...


class SQLAuditLogTable(SQLAuditBase):
    __tablename__ = "SQLAuditTables"

    table_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    record_id_field: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=True)
    fields: Mapped[list["SQLAuditLogField"]] = relationship(back_populates="table")


class SQLAuditLogField(SQLAuditBase):
    __tablename__ = "SQLAuditFields"

    field_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("SQLAuditTables.table_id"))
    field_name: Mapped[str] = mapped_column(String)

    table: Mapped["SQLAuditLogTable"] = relationship(
        back_populates="fields",
    )

    logs: Mapped[list["SQLAuditLog"]] = relationship(
        back_populates="field",
    )


class SQLAuditLog(SQLAuditBase):
    __tablename__ = "SQLAuditLogs"

    audit_log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    field_id: Mapped[int] = mapped_column(ForeignKey("SQLAuditFields.field_id"))
    field: Mapped["SQLAuditLogField"] = relationship(
        back_populates="logs",
    )

    record_id: Mapped[str] = mapped_column(String)
    old_value: Mapped[JSON | None] = mapped_column(JSON)
    new_value: Mapped[JSON | None] = mapped_column(JSON)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    changed_by: Mapped[str | None] = mapped_column(String, nullable=True)
