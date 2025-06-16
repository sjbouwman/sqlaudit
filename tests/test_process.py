import datetime
import uuid

from sqlaudit.process import _audit_changes_values_encoder


def test_audit_change_encoder():
    changes = [
        uuid.uuid4(),
        datetime.datetime.now(),
        "test_string",
        123,
        [1, 2, 3],
        {"key": "value"},
    ]

    encoded_changes = _audit_changes_values_encoder(changes)

    assert isinstance(encoded_changes, str), "Encoded changes should be a list."
    assert all(isinstance(change, str) for change in encoded_changes), (
        "All encoded changes should be strings."
    )

    
