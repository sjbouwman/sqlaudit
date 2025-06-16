import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

type ResourceIdType = str | int | uuid.UUID

_allowed_dtypes = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": json.loads,
}


class SQLAuditChange(BaseModel):
    """
    Represents a change in the audit log.
    """

    field_name: Annotated[str, Field(description="Name of the field that was changed")]

    dtype: Annotated[
        str,
        Field(description="Data type of the field, e.g., 'string', 'integer', etc."),
    ]

    old_value: Annotated[
        Any, Field(description="List of string values before the change")
    ]

    new_value: Annotated[
        Any, Field(description="List of string values after the change")
    ]

    @model_validator(mode="after")
    def _validate_values(self) -> Self:
        """
        Validate and normalize old_value and new_value based on their data type.
        Convert empty strings to None and ensure proper deserialization for dicts.
        """
        for field in ["old_value", "new_value"]:
            value = getattr(self, field)
            if value is None or value == "":
                setattr(self, field, None)
                continue

            assert self.dtype in _allowed_dtypes, (
                f"Unsupported dtype: {self.dtype}. Available types: {', '.join(_allowed_dtypes.keys())}"
            )

            target_type = _allowed_dtypes[self.dtype]

            setattr(self, field, target_type(value))

        return self

    model_config = ConfigDict(from_attributes=True)


class SQLAuditRecord(BaseModel):
    """
    Represents a record in the audit log.
    """

    record_id: Annotated[
        uuid.UUID,
        Field(
            description="Unique identifier for the audit log record, used to track changes",
            alias="record_id",
        ),
    ]

    resource_id: Annotated[str, Field(description="Primary key of the affected record")]

    resource_type: Annotated[
        str,
        Field(
            description="Type of the resource, e.g., 'User', 'Customer', etc. Will be the table_label if available, else the table_name"
        ),
    ]

    timestamp: Annotated[datetime, Field(description="Timestamp of the change")]

    changed_by: Annotated[
        str | None,
        Field(default=None, description="ID of the user who made the change"),
    ]

    impersonated_by: Annotated[
        str | None,
        Field(
            default=None,
            description="ID of the user who is impersonating another user (optional)",
        ),
    ]

    reason: Annotated[
        str | None,
        Field(
            default=None,
            description="Reason for the change, if provided (optional)",
        ),
    ]

    changes: Annotated[
        list[SQLAuditChange],
        Field(
            description="List of changes made to the resource, each change is represented by a SQLAuditChange object",
            validation_alias="field_changes",
        ),
    ]

    model_config = ConfigDict(from_attributes=True)


@dataclass
class SQLAuditOptions:
    tracked_fields: list[str] | None = None
    resource_id_field: str | None = None
    user_id_field: str | None = None
    table_label: str | None = None

    def __post_init__(self):
        if self.tracked_fields is not None:
                if not isinstance(self.tracked_fields, list) or not all(
                    isinstance(field, str) for field in self.tracked_fields
                ):
                    raise TypeError(
                        "SQLAuditOptions.tracked_fields must be either None or a list of strings. "
                        f"Got {type(self.tracked_fields).__name__}."
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
