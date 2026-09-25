"""Muscle rings (ADR-020): this week's logged sets per major muscle against the weekly target.

Borrowed from Apple's Activity rings and Bevel's muscle distribution, but counted from what the
athlete logged, never estimated. A working or extra set with at least one rep counts fully for its
exercise's primary muscles and at the bundle's synergist credit for the others, exactly as the
weekly planner counts them (ADR-017). Warm-up sets and zero-rep attempts do not count.

The target is the bundle's cited weekly target for the athlete's goal and experience, and
``planned`` is what the accepted week prescribes, so the ring shows both the aim and the plan.
The week starts on the athlete's local Monday, which needs the host's UTC offset. Without it,
or without a weekly planner, there are no rings rather than rings for the wrong week.
"""

from __future__ import annotations

import math
from typing import Any

from .content import exercises_by_id
from .rules.adaptation import local_weekday

JSON = dict[str, Any]

DAY = 86400.0
COUNTED_KINDS = ("working", "extra")


def muscle_rings(
    state: JSON, library: JSON, now: float, day_start: float | None, utc_offset: int | None
) -> JSON | None:
    """``{weekStart, muscles: [{muscle, done, planned, target}]}`` for the major muscles, or ``None``."""
    planner = library.get("planner")
    profile = state.get("profile")
    if planner is None or profile is None or utc_offset is None:
        return None
    target = (planner["targets"].get(profile["goal"]) or {}).get(profile["experience"])
    if target is None:
        return None
    week_start = local_week_start(now, day_start, utc_offset)
    credits = _credits_by_exercise(library)
    done = _logged_this_week(state, credits, week_start, now)
    planned = _planned_per_week(state, credits)
    return {
        "weekStart": week_start,
        "muscles": [
            {
                "muscle": muscle,
                "done": round(done.get(muscle, 0.0), 2),
                "planned": round(planned.get(muscle, 0.0), 2),
                "target": target,
            }
            for muscle in planner["structures"]["majorMuscles"]
        ],
    }


def local_week_start(now: float, day_start: float | None, utc_offset: int) -> float:
    """The athlete's local Monday 00:00, in reference seconds.

    ``day_start`` (local midnight today, from the host) is used when given; otherwise it is
    derived from ``utc_offset``.
    """
    today = day_start if day_start is not None else math.floor((now + utc_offset) / DAY) * DAY - utc_offset
    return today - local_weekday(now, utc_offset) * DAY


def _credits_by_exercise(library: JSON) -> dict[str, dict[str, float]]:
    """Exercise id -> muscle credits of its planner role (exercises outside the planner count nothing)."""
    roles = library["planner"]["structures"]["roles"]
    credits: dict[str, dict[str, float]] = {}
    for exercise_id, exercise in exercises_by_id(library).items():
        role = roles.get(exercise["role"])
        if role is not None:
            credits[exercise_id] = role["muscles"]
    return credits


def _logged_this_week(
    state: JSON, credits: dict[str, dict[str, float]], week_start: float, now: float
) -> dict[str, float]:
    totals: dict[str, float] = {}
    for session in state["sessions"]:
        exercise_by_slot = {slot["id"]: slot["exerciseID"] for slot in session["plan"]["slots"]}
        for log in session["logs"]:
            if log["kind"] not in COUNTED_KINDS or log["reps"] < 1 or not week_start <= log["occurredAt"] <= now:
                continue
            for muscle, credit in credits.get(exercise_by_slot.get(log["prescriptionID"], ""), {}).items():
                totals[muscle] = totals.get(muscle, 0.0) + credit
    return totals


def _planned_per_week(state: JSON, credits: dict[str, dict[str, float]]) -> dict[str, float]:
    """Sets a week the accepted weekly plan prescribes, per muscle (one pass over every plan)."""
    program = state.get("program")
    totals: dict[str, float] = {}
    if not program or not any(plan.get("weekday") is not None for plan in program["plans"]):
        return totals
    for plan in program["plans"]:
        for slot in plan["slots"]:
            for muscle, credit in credits.get(slot["exerciseID"], {}).items():
                totals[muscle] = totals.get(muscle, 0.0) + credit * slot["workingSets"]
    return totals
