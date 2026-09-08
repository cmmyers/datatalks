import datetime

from django.utils import timezone


def current_week_start():
    """Return the date of the Monday on or before today (server local time).

    Weeks run Monday-Sunday, server local time, per the spec — hardcoded,
    not configurable. Used by the complete-chore endpoint (task 12) to stamp
    WeeklyCompletion.week_start_date, and reused by task 14's weekly-rollover
    logic and task 13's points board rather than either introducing a
    competing week-boundary calculation.
    """
    today = timezone.localdate()
    return today - datetime.timedelta(days=today.weekday())
