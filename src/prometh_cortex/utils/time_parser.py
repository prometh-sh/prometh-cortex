"""Utility functions for parsing time expressions."""

from datetime import datetime, timedelta
from typing import Optional, Tuple


def parse_relative_time(expr: str) -> Optional[float]:
    """Parse relative time expressions like '7d', '2w', '24h'.

    Args:
        expr: Time expression (e.g., '7d', '2w', '24h')

    Returns:
        Unix timestamp of the calculated time, or None if parsing fails
    """
    expr = expr.strip().lower()

    # Extract number and unit
    i = 0
    while i < len(expr) and expr[i].isdigit():
        i += 1

    if i == 0 or i == len(expr):
        return None

    try:
        number = int(expr[:i])
        unit = expr[i:].strip()

        if unit == "d":
            delta = timedelta(days=number)
        elif unit == "w":
            delta = timedelta(weeks=number)
        elif unit == "h":
            delta = timedelta(hours=number)
        elif unit == "m":
            delta = timedelta(minutes=number)
        else:
            return None

        target_time = datetime.utcnow() - delta
        return target_time.timestamp()
    except (ValueError, AttributeError):
        return None


def parse_absolute_date(date_str: str) -> Optional[float]:
    """Parse absolute date strings like '2026-03-01'.

    Args:
        date_str: Date string in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)

    Returns:
        Unix timestamp, or None if parsing fails
    """
    date_str = date_str.strip()

    try:
        # Try ISO datetime format first
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            # Assume date-only format, set to start of day
            dt = datetime.fromisoformat(date_str)

        return dt.timestamp()
    except (ValueError, AttributeError):
        return None


def parse_time_filter(time_expr: str) -> Optional[float]:
    """Parse either relative or absolute time expression.

    Tries relative format first (7d, 2w), then absolute format (2026-03-01).

    Args:
        time_expr: Time expression (relative or absolute)

    Returns:
        Unix timestamp, or None if parsing fails
    """
    if not time_expr:
        return None

    # Try relative format first
    ts = parse_relative_time(time_expr)
    if ts is not None:
        return ts

    # Try absolute format
    ts = parse_absolute_date(time_expr)
    if ts is not None:
        return ts

    return None


def format_timestamp(ts: float) -> str:
    """Format a Unix timestamp as a human-readable date string.

    Args:
        ts: Unix timestamp

    Returns:
        ISO format date string
    """
    dt = datetime.utcfromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
