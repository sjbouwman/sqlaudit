import uuid

import pytest

from sqlaudit._internals.utils import (
    ensure_valid_resource_ids,
)




def test_ensure_valid_resource_ids():
    """
    Test the retrieval of resource changes with valid resource IDs.
    This test checks if the get_resource_changes function correctly retrieves changes for valid resource IDs.
    """
    unique_id = uuid.uuid4()
    ids = ensure_valid_resource_ids([1, "2", unique_id]) 
    assert len(ids) == 3, f"Expected all valid resource IDs in list, got {ids}"

    ids = ensure_valid_resource_ids("1")
    assert len(ids) == 1 and ids[0] == "1", "Expected single valid resource ID in list"
    
    
    ids = ensure_valid_resource_ids(None) # Is valid as it will be ignored in the retrieval function
    assert len(ids) == 0, "Expected empty list for None input"

def test_ensure_invalid_resource_ids():
    """
    Test the retrieval of resource changes with invalid resource IDs.
    This test checks if the get_resource_changes function raises an error for invalid resource IDs.
    """
    with pytest.raises(TypeError):
        ensure_valid_resource_ids(["valid", 2.5, None]) # type: ignore

    with pytest.raises(TypeError):
        ensure_valid_resource_ids(2.5)  # type: ignore

    
