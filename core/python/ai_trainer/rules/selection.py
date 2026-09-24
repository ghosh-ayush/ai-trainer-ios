"""Choosing an exercise for a role, and the per-goal prescription, for every program path.

Both the one-session template (``program``) and the weekly planner (``week_program``) pick
exercises the same way, so an athlete's equipment, exclusions and preferences mean the same
thing whichever path builds their program.
"""

from __future__ import annotations

from typing import Any

from ..content import is_enabled

JSON = dict[str, Any]


def first_eligible_exercise(role: str, profile: JSON, library: JSON) -> JSON | None:
    """Enabled exercise for ``role`` matching the athlete's equipment; preferred first, then by id."""
    eligible = [
        exercise
        for exercise in library["exercises"]
        if exercise["role"] == role
        and is_enabled(exercise["review"], library)
        and exercise["equipmentKind"] in profile["equipment"]
        and exercise["id"] not in profile["excludedExercises"]
    ]
    eligible.sort(key=lambda exercise: (exercise["id"] not in profile["preferredExercises"], exercise["id"]))
    return eligible[0] if eligible else None


def prescription(template: JSON, goal: str) -> JSON:
    """The goal's own prescription when the template gives one (``slotByGoal``), else the shared ``slot``."""
    by_goal: JSON = template.get("slotByGoal") or {}
    chosen: JSON = by_goal.get(goal) or template["slot"]
    return chosen
