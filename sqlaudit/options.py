from dataclasses import dataclass


@dataclass
class SQLAuditOptionsBase:
    tracked_fields: list[str]
    record_id_field: str | None
    user_id_field: str | None
    table_label: str | None = None


@dataclass
class SQLAuditOptions:
    tracked_fields: list[str]
    record_id_field: str
    user_id_field: str | None = None
    table_label: str | None = None


def convert_base_to_sql_audit_options(
    options: SQLAuditOptionsBase,
) -> SQLAuditOptions:
    """
    Converts SQLAuditOptionsBase to SQLAuditOptions.
    """
    if not isinstance(options, SQLAuditOptionsBase):
        raise TypeError("options must be an instance of SQLAuditOptionsBase.")

    if not isinstance(options.tracked_fields, list):
        raise TypeError("tracked_fields must be a list.")

    if not isinstance(options.record_id_field, str):
        raise TypeError("record_id_field must be a string.")

    if options.user_id_field is not None and not isinstance(options.user_id_field, str):
        raise TypeError("user_id_field must be a string or None.")

    if options.table_label is not None and not isinstance(options.table_label, str):
        raise TypeError("table_label must be a string or None.")

    return SQLAuditOptions(
        tracked_fields=options.tracked_fields,
        record_id_field=options.record_id_field,
        user_id_field=options.user_id_field,
        table_label=options.table_label,
    )