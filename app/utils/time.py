from datetime import datetime, timezone

def utc_now():
    """Return a timezone-aware UTC datetime object."""
    return datetime.now(timezone.utc)
