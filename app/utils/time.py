from datetime import datetime, timezone

def utc_now():
    """Return a timezone-aware UTC datetime object."""
    return datetime.now(timezone.utc)
    
def fridays_in_month(year: int, month: int) -> int:
    """Return the number of Fridays in the given month/year.

    Friday is weekday() == 4 (Monday=0)."""
    import calendar
    cal = calendar.Calendar(firstweekday=0)
    return sum(1 for day in cal.itermonthdates(year, month) if day.month == month and day.weekday() == 4)
