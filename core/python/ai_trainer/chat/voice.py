"""Chat replies in the model's own words, checked against the app's facts (ADR-027).

The core writes each answer as plain facts (``ChatReply.lines``). Apple's on-device model may
rewrite them as a conversational reply, strictly and deterministically. This module decides
whether that wording may be shown. The facts stay one tap away either way:

- Every number in the wording must appear in the facts or in the athlete's own words.
- Every exercise the wording names must appear in the facts or in the athlete's words.
- Pain answers are never reworded: the app's safety wording stands exactly (owner's decision).
- Empty, overlong or linked text is refused.

A refused wording is dropped, and the host shows the app's facts instead. The check never edits
the wording; it only accepts or refuses it.
"""

from __future__ import annotations

import math
from typing import Any

from ..spoken_sets import spoken_numbers
from ..wording import fold

JSON = dict[str, Any]

MAX_WORDING = 900


def check_wording(reply: JSON, wording: str, message: str, library: JSON, earlier: str | None = None) -> JSON:
    """``ChatWording``: the model's wording when every number and exercise in it is grounded."""
    text = wording.strip()
    if reply["topic"] == "pain":
        return _refused(["pain answers keep the app's wording"])
    if not text:
        return _refused(["empty"])
    if len(text) > MAX_WORDING:
        return _refused(["too long"])
    if "http" in text.casefold() or "www." in text.casefold():
        return _refused(["a link"])
    grounds = " ".join([reply["reading"], *reply["lines"], message, earlier or ""])
    dropped = _ungrounded_numbers(text, grounds) + _ungrounded_exercises(text, grounds, library)
    if dropped:
        return _refused(dropped)
    return {"text": text, "accepted": True, "dropped": []}


def _ungrounded_numbers(text: str, grounds: str) -> list[str]:
    allowed = spoken_numbers(grounds)
    missing: list[str] = []
    for number in spoken_numbers(text):
        if not any(math.isclose(number, known, abs_tol=1e-9) for known in allowed):
            missing.append(f"{number:g}")
    return missing


def _ungrounded_exercises(text: str, grounds: str, library: JSON) -> list[str]:
    said, known = fold(text), fold(grounds)
    return [
        exercise["name"]
        for exercise in library["exercises"]
        if fold(exercise["name"]) in said and fold(exercise["name"]) not in known
    ]


def _refused(dropped: list[str]) -> JSON:
    return {"text": "", "accepted": False, "dropped": dropped}
