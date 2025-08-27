import datetime
from typing import Any, get_args
import uuid

from sqlalchemy import TIMESTAMP, ForeignKey, String
from sqlalchemy.ext.hybrid import hybrid_property

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from uuid_utils import uuid7
from sqlaudit._internals.registry import audit_model_registry

def uuid7_stdlib():
    return uuid.UUID(bytes=uuid7().bytes)


class SQLAuditBase(DeclarativeBase): ...


class SQLAuditLogTable(SQLAuditBase):
    __tablename__ = "SQLAuditTables"

    table_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    resource_id_field: Mapped[str] = mapped_column(String, nullable=False)
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


class SQLAuditLog(SQLAuditBase):
    __tablename__ = "SQLAuditLogs"

    record_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7_stdlib)

    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("SQLAuditTables.table_id"))
    table: Mapped["SQLAuditLogTable"] = relationship()

    resource_id: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
    )

    changed_by: Mapped[str | None] = mapped_column(String(256))
    impersonated_by: Mapped[str | None] = mapped_column(String(256))
    reason: Mapped[str | None] = mapped_column(String(512))

    field_changes: Mapped[list["SQLAuditLogFieldChange"]] = relationship(
        "SQLAuditLogFieldChange",
        back_populates="audit_log",
        cascade="all, delete-orphan",
    )

    @hybrid_property
    def resource_type(self) -> str:
        """
        Returns the type of resource being audited, which is the name of the table.
        """
        return self.table.label or self.table.table_name


class SQLAuditLogFieldChange(SQLAuditBase):
    __tablename__ = "SQLAuditFieldChanges"

    change_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("SQLAuditLogs.record_id"))

    field_id: Mapped[int] = mapped_column(ForeignKey("SQLAuditFields.field_id"))
    field: Mapped["SQLAuditLogField"] = relationship()

    old_value: Mapped[str | None] = mapped_column()
    new_value: Mapped[str | None] = mapped_column()

    audit_log: Mapped["SQLAuditLog"] = relationship(
        back_populates="field_changes",
    )

    @hybrid_property
    def field_name(self) -> str:
        """
        Returns the name of the field associated with this change.
        """
        return self.field.field_name

    
    @hybrid_property
    def python_type(self) -> Any:
        """
        Returns the data type of the field associated with this change.
        """

        model = audit_model_registry.from_table_name(self.field.table.table_name).table_model

        annotations = model.__annotations__.get(self.field.field_name)
        if not annotations:
            return None
                    
        inner_type = get_args(annotations)
        
        return inner_type[0]