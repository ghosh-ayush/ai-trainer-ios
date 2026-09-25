"""Small wording helpers shared by the modules that write sentences for the athlete.

Weekdays use the core's numbering: 0 is Monday (ADR-017). The short names also form week-option
ids ("Mon-fullBodyA"), so they must not change.
"""

from __future__ import annotations

WEEKDAY_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def join_words(items: list[str]) -> str:
    """``A``, ``A and B``, ``A, B and C``."""
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def fold(text: str) -> str:
    """``text`` trimmed and case-folded, for comparing names the athlete or a model wrote."""
    return text.strip().casefold()
