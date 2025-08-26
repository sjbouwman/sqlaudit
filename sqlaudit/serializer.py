from collections.abc import Callable
from dataclasses import dataclass
import datetime
from typing import Any
import json
import uuid

@dataclass
class TypeHandler:
    serialize: Callable[[Any], str]
    deserialize: Callable[[str], Any]

class Serializer:

    _builtins: dict[type, TypeHandler] = {
        str: TypeHandler(
            serialize=lambda v: v,
            deserialize=lambda v: v
        ),
        int: TypeHandler(
            serialize=str,
            deserialize=int
        ),
        float: TypeHandler(
            serialize=str,
            deserialize=float
        ),
        bool: TypeHandler(
            serialize=lambda v: "1" if v else "0",  # Store bools as '1' or '0'
            deserialize=lambda v: v == "1"
        ),
        datetime.datetime: TypeHandler(
            serialize=lambda v: v.isoformat(),
            deserialize=lambda v: datetime.datetime.fromisoformat(v)
        ),
        datetime.date: TypeHandler(
            serialize=lambda v: v.isoformat(),
            deserialize=lambda v: datetime.date.fromisoformat(v)
        ),
        dict: TypeHandler(
            serialize=lambda v: json.dumps(v),
            deserialize=lambda v: json.loads(v)
        ),
        list: TypeHandler(
            serialize=lambda v: json.dumps(v),
            deserialize=lambda v: json.loads(v)
        ),
        uuid.UUID: TypeHandler(
            serialize=lambda v: str(v),
            deserialize=lambda v: uuid.UUID(v)
        ),
    }

    _custom_handlers: dict[type, TypeHandler] = {}

    @classmethod
    def get_handler(cls, target_type: type) -> TypeHandler | None:
        """
        Retrieves the handler for a specific type
        """
        return cls._custom_handlers.get(target_type) or cls._builtins.get(target_type)

    @classmethod
    def serialize(cls, value: Any) -> str | None:
        """
        Serializes a value to string representation
        """
        if value is None:
            return None
        
        handler = cls.get_handler(type(value))
        if not handler:
            raise TypeError(f"Value of type {type(value)} is not serializable")

        return handler.serialize(value)

    @classmethod
    def deserialize(cls, value: str | None, target_type: type) -> Any:
        """
        Deserializes a string representation back to the target type
        """
        if value is None:
            return None
        
        handler = cls.get_handler(target_type)
        if not handler:
            raise TypeError(f"Type {target_type} is not deserializable")

        safe_value = value if value is not None else "null"
        return handler.deserialize(safe_value)

    @classmethod
    def register_custom_handler(cls, target_type: type, handler: TypeHandler) -> None:
        """
        Registers a custom handler for a specific type
        """
        cls._custom_handlers[target_type] = handler


    @classmethod
    def is_serializable(cls, value: Any) -> bool:
        """
        Checks if a value can be serialized by the Serializer
        """
        if value is None:
            return True
        return cls.get_handler(type(value)) is not None
    
    @classmethod
    def has_handler(cls, target_type: type) -> bool:
        """
        Checks if a handler exists for a specific type
        """
        return cls.get_handler(target_type) is not None