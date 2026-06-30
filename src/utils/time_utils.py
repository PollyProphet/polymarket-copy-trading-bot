"""
Time and timezone utilities.

Provides timestamp parsing and timezone conversion functions.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Union

from src.logger import log

# Define UTC+8 timezone (for display purposes)
TIMEZONE_UTC8 = timezone(timedelta(hours=8))


def parse_timestamp(ts: Union[datetime, str, int, float]) -> Optional[datetime]:
    """
    Parse timestamp to datetime object.

    Args:
        ts: Timestamp (can be datetime, string, or numeric)

    Returns:
        Parsed datetime object, or None if parsing fails

    Examples:
        >>> parse_timestamp("2024-01-01T00:00:00Z")
        datetime.datetime(2024, 1, 1, 0, 0, tzinfo=...)

        >>> parse_timestamp(1704067200)
        datetime.datetime(2024, 1, 1, 0, 0, tzinfo=...)
    """
    try:
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts
        elif isinstance(ts, str):
            parsed = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        elif isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception as e:
        log.warning(f"Failed to parse timestamp: {ts}, error: {e}")

    return None


def advance_checkpoint(timestamp: datetime) -> datetime:
    """
    Advance checkpoint past the last processed activity to avoid duplicates.

    Polymarket activity queries use an inclusive start time, so the next poll
    would re-fetch activities that share the same timestamp unless we move
    the checkpoint forward slightly.

    Args:
        timestamp: Latest processed activity timestamp

    Returns:
        Checkpoint value safe to use as the next query start time
    """
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return timestamp + timedelta(microseconds=1)


def to_utc8(dt: datetime) -> datetime:
    """
    Convert datetime to UTC+8 timezone.

    Args:
        dt: Datetime object

    Returns:
        Datetime converted to UTC+8 timezone
    """
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(TIMEZONE_UTC8)


def get_latest_timestamp(activities: list) -> Optional[datetime]:
    """
    Extract the latest timestamp from a list of activities.

    Args:
        activities: List of activity objects

    Returns:
        Latest timestamp, or None if unable to parse

    Example:
        >>> activities = [Activity(timestamp="2024-01-01"), Activity(timestamp="2024-01-02")]
        >>> get_latest_timestamp(activities)
        datetime.datetime(2024, 1, 2, ...)
    """
    if not activities:
        return None

    try:
        timestamps = []
        for activity in activities:
            ts = getattr(activity, 'timestamp', None)
            if ts:
                parsed_ts = parse_timestamp(ts)
                if parsed_ts:
                    timestamps.append(parsed_ts)

        return max(timestamps) if timestamps else None

    except Exception as e:
        log.warning(f"Error getting latest timestamp: {e}")
        return None


def format_timestamp_for_display(ts: Union[datetime, str, int, float, None]) -> str:
    """
    Format timestamp for display in UTC+8 timezone.

    Args:
        ts: Timestamp in various formats

    Returns:
        Formatted timestamp string, or 'N/A' if invalid

    Example:
        >>> format_timestamp_for_display("2024-01-01T00:00:00Z")
        '2024-01-01 08:00:00'
    """
    if ts is None:
        return 'N/A'

    try:
        if isinstance(ts, datetime):
            timestamp = to_utc8(ts)
        elif isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            timestamp = to_utc8(dt)
        elif isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            timestamp = to_utc8(dt)
        else:
            return 'N/A'

        return timestamp.strftime('%Y-%m-%d %H:%M:%S')

    except Exception:
        return 'N/A'
