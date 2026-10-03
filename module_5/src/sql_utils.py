"""Shared limit rules for every query the project runs."""

MAX_LIMIT = 100
DEFAULT_LIMIT = 10


def clamp_limit(value, default=DEFAULT_LIMIT):
    """Turn any requested row limit into a whole number from 1 to MAX_LIMIT.

    Args:
        value: The requested limit. Can be any type, since it may come from
            a user.
        default: Used when value cannot be read as a whole number.

    Returns:
        An int between 1 and MAX_LIMIT.
    """
    try:
        number = int(value)
    except (ValueError, TypeError, OverflowError):
        return default
    return max(1, min(number, MAX_LIMIT))
