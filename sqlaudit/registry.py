from dataclasses import dataclass

from sqlalchemy.orm import DeclarativeBase




@dataclass
class SQLAuditOptions:
    tracked_fields: list[str]
    resource_id_field: str | None = None
    user_id_field: str | None = None
    table_label: str | None = None

    def __post_init__(self):
        if not isinstance(self.tracked_fields, list) or not all(
            isinstance(field, str) for field in self.tracked_fields
        ):
            raise TypeError(
                "SQLAuditOptions.tracked_fields must be a list[str]. Got %r."
                % type(self.tracked_fields).__name__
            )
        if (
            not isinstance(self.resource_id_field, str)
            and self.resource_id_field is not None
        ):
            raise TypeError(
                "SQLAuditOptions.resource_id_field must be a 'str' or 'None'. Got %r."
                % type(self.resource_id_field).__name__
            )

        if self.user_id_field is not None and not isinstance(self.user_id_field, str):
            raise TypeError(
                "SQLAuditOptions.user_id_field must be a 'str' or 'None'. Got %r."
                % type(self.user_id_field).__name__
            )

        if self.table_label is not None and not isinstance(self.table_label, str):
            raise TypeError(
                "SQLAuditOptions.table_label must be a 'str' or 'None'. Got %r."
                % type(self.table_label).__name__
            )


@dataclass
class AuditTableEntry:
    table_model: type[DeclarativeBase]
    options: SQLAuditOptions

