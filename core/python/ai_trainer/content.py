"""Content library gating: which exercises and policies may drive guidance.

A ``review`` status of ``approved`` is always usable. ``fixture`` content is
test data and is usable only when the host says fixtures are permitted
(Debug builds). Everything else is disabled.
"""

from __future__ import annotations

from typing import Any

JSON = dict[str, Any]


def is_enabled(review_status: str, library: JSON) -> bool:
    if review_status == "approved":
        return True
    return review_status == "fixture" and bool(library["permitsFixtures"])


def policy_is_enabled(library: JSON) -> bool:
    return is_enabled(library["policy"]["review"], library)


def exercises_by_id(library: JSON) -> dict[str, JSON]:
    return {exercise["id"]: exercise for exercise in library["exercises"]}


def find_exercise(library: JSON, exercise_id: str) -> JSON | None:
    return exercises_by_id(library).get(exercise_id)
