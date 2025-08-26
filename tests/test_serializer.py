





import datetime
import json
import uuid
from sqlaudit.serializer import Serializer, TypeHandler


def test_integer_serialization():
    assert Serializer.is_serializable(42) is True
    assert Serializer.serialize(42) == "42"
    assert Serializer.deserialize("42", int) == 42


def test_float_serialization():
    assert Serializer.is_serializable(42.0) is True
    assert Serializer.serialize(42.0) == "42.0"
    assert Serializer.deserialize("42.0", float) == 42.0

def test_string_serialization():
    assert Serializer.is_serializable("Hello, world!") is True
    assert Serializer.serialize("Hello, world!") == "Hello, world!"
    assert Serializer.deserialize("Hello, world!", str) == "Hello, world!"

def test_bool_serialization():
    assert Serializer.is_serializable(True) is True
    assert Serializer.serialize(True) == "1"
    assert Serializer.deserialize("1", bool) is True

    assert Serializer.is_serializable(False) is True
    assert Serializer.serialize(False) == "0"
    assert Serializer.deserialize("0", bool) is False

def test_none_serialization():
    assert Serializer.is_serializable(None) is True
    assert Serializer.serialize(None) is None
    assert Serializer.deserialize(None, type(None)) is None

def test_list_serialization():
    assert Serializer.is_serializable([1, 2, 3]) is True
    assert Serializer.serialize([1, 2, 3]) == "[1, 2, 3]"
    assert Serializer.deserialize("[1, 2, 3]", list) == [1, 2, 3]

    assert Serializer.serialize([["a"], ["b"]]) == '[["a"], ["b"]]'
    assert Serializer.deserialize('[["a"], ["b"]]', list) == [["a"], ["b"]]

def test_dict_serialization():
    assert Serializer.is_serializable({"key": "value"}) is True
    assert Serializer.serialize({"key": "value"}) == '{"key": "value"}'
    assert Serializer.deserialize('{"key": "value"}', dict) == {"key": "value"}

    assert Serializer.serialize({"a": 1, "b": 2}) == '{"a": 1, "b": 2}'
    assert Serializer.deserialize('{"a": 1, "b": 2}', dict) == {"a": 1, "b": 2}

def test_non_serializable():
    assert Serializer.is_serializable(set()) is False

    # We test if we get an error when attempting to serialize
    try:
        Serializer.serialize(set())
    except TypeError:
        pass
    else:
        assert False, "Expected TypeError"

    try:
        Serializer.deserialize("{a,b,c}", set)
    except TypeError:
        pass
    else:
        assert False, "Expected TypeError"


def test_datetime_serialization():
    dt = datetime.datetime.now()

    assert Serializer.is_serializable(dt) is True
    assert Serializer.serialize(dt) == dt.isoformat()
    assert Serializer.deserialize(dt.isoformat(), datetime.datetime) == dt

def test_date_serialization():
    dt = datetime.date.today()

    assert Serializer.is_serializable(dt) is True
    assert Serializer.serialize(dt) == dt.isoformat()
    assert Serializer.deserialize(dt.isoformat(), datetime.date) == dt

def test_uuid_serialization():
    uuid_value = uuid.uuid4()

    assert Serializer.is_serializable(uuid_value) is True
    assert Serializer.serialize(uuid_value) == str(uuid_value)
    assert Serializer.deserialize(str(uuid_value), uuid.UUID) == uuid_value

def test_custom_type_serialization():
    class CustomType:
        def __init__(self, value: int):
            self.value = value

        def __eq__(self, other: object):
            if not isinstance(other, CustomType):
                return NotImplemented
            return self.value == other.value

    custom_value = CustomType(42)

    # First this should not be serializable as we did not register the type. Later we should be able
    assert Serializer.is_serializable(custom_value) is False

    Serializer.register_custom_handler(CustomType, TypeHandler(
        serialize=lambda v: json.dumps({"value": v.value}),
        deserialize=lambda v: CustomType(**json.loads(v))
    ))

    assert Serializer.is_serializable(custom_value) is True
    assert Serializer.serialize(custom_value) == '{"value": 42}'
    assert Serializer.deserialize('{"value": 42}', CustomType) == custom_value