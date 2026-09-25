"""The buttons under a chat answer (``ChatAction``). Each needs the athlete's tap."""

from __future__ import annotations

from typing import Any

JSON = dict[str, Any]

# The questions offered when the app cannot tell what was asked, and as starters in the host.
STARTERS: tuple[tuple[str, str], ...] = (
    ("How is my training going?", "exerciseProgress"),
    ("What's my next workout?", "nextSession"),
    ("What's my week?", "week"),
    ("I have less time today", "lessTime"),
    ("Something hurts", "pain"),
    ("I'm sick or away", "away"),
    ("Where do the numbers come from?", "evidence"),
)


def ask_exercise(name: str) -> JSON:
    """A follow-up question about one exercise, sent with its draft so it skips the model."""
    return ask(f"How is {name} going?", {"topic": "exerciseProgress", "exercise": name})


def ask(message: str, draft: JSON) -> JSON:
    """An ``ask`` action: tapping it sends ``message`` with ``draft`` as a new question."""
    return action("ask", message, message=message, draft=draft)


def action(kind: str, title: str, **fields: Any) -> JSON:
    """A ``ChatAction``; fields set to ``None`` are left out."""
    action: JSON = {"kind": kind, "title": title}
    action.update({key: value for key, value in fields.items() if value is not None})
    return action
