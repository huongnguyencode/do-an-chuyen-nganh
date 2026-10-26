from typing import Any


def values_equal(actual: Any, expected: Any) -> bool:
    """So sánh JSON theo cả kiểu và giá trị; `True` khác `1`."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            values_equal(left, right) for left, right in zip(actual, expected, strict=True)
        )
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            values_equal(actual[key], expected[key]) for key in expected
        )
    return actual == expected
