"""TB-01: initial program selection.

The program is built from the content bundle's ``template``: one repeating
full-body session with one exercise per required role and an optional
accessory. Every number (sets, reps, rest, minutes) comes from the template —
per goal when it has ``slotByGoal``, otherwise its shared ``slot``;
none is defined here. Reviewed multi-day templates arrive with the
evidence-based content bundle (Track C).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..athlete_state import equipment_context
from ..content import is_enabled, policy_is_enabled
from ..errors import DomainError
from .selection import first_eligible_exercise, prescription
from .week_program import week_program

JSON = dict[str, Any]

# IDs the host must supply: program, plan, then up to four slots.
REQUIRED_ID_COUNT = 6


def initial_program(profile: JSON, library: JSON, now: float, ids: Iterable[str], option_id: str | None = None) -> JSON:
    """Build the initial Program for ``profile`` or raise ``DomainError``.

    A bundle with a weekly ``planner`` (ADR-017) builds one plan per session of the week
    ``option_id`` names (the best week when ``None``); ``ids[0]`` is the program id and the rest
    supply plans and slots in order. Otherwise the one-session template is used: ``ids[0]`` is
    the program id, ``ids[1]`` the plan id, ``ids[2:]`` slot ids, and ``option_id`` must be absent.
    """
    if not policy_is_enabled(library):
        raise DomainError("unsupported")  # approved content, or fixtures where the host permits them
    if "planner" in library:
        return week_program(profile, library, now, ids, option_id)
    if option_id is not None:
        raise DomainError("invalid", "This content has no weekly options to choose from.")
    ids = list(ids)
    template = library["template"]
    _require_supported_profile(profile, template)

    selected: list[tuple[JSON, bool]] = []
    for role in template["requiredRoles"]:
        exercise = first_eligible_exercise(role, profile, library)
        if exercise is None:
            raise DomainError("unsupported")
        selected.append((exercise, False))

    accessory = _eligible_accessory(profile, library, template["accessory"])
    if accessory is not None:
        selected.append((accessory, True))

    slots = [
        _slot(ids[index + 2], exercise, profile["preferredUnit"], optional, prescription(template, profile["goal"]))
        for index, (exercise, optional) in enumerate(selected)
    ]
    plan = {
        "id": ids[1],
        "revision": 1,
        "name": template["name"],
        "slots": slots,
        "modified": False,
        "warmUpMinutes": template["warmUpMinutes"],
    }
    return {
        "id": ids[0],
        "revision": 1,
        "templateID": template["id"],
        "libraryVersion": library["policy"]["version"],
        "plans": [plan],
        "sequenceIndex": 0,
        "acceptedAt": now,
    }


def _slot(slot_id: str, exercise: JSON, unit: str, optional: bool, prescription: JSON) -> JSON:
    """One prescription slot from the template. The working load starts unknown."""
    return {
        "id": slot_id,
        "exerciseID": exercise["id"],
        "equipment": equipment_context(exercise, unit),
        "protocolID": prescription["protocolID"],
        "workingSets": prescription["workingSets"],
        "lowerReps": prescription["lowerReps"],
        "upperReps": prescription["upperReps"],
        "targets": [prescription["lowerReps"]] * prescription["workingSets"],
        "restSeconds": prescription["restSeconds"],
        "optional": optional,
        "estimatedMinutes": prescription["estimatedMinutes"],
    }


def _require_supported_profile(profile: JSON, template: JSON) -> None:
    supported = (
        profile["adultConfirmed"]
        and profile["supportedScopeConfirmed"]
        and profile["goal"] in template["supportedGoals"]
        and template["minDaysPerWeek"] <= profile["daysPerWeek"] <= template["maxDaysPerWeek"]
        and profile["minutes"] >= template["minSessionMinutes"]
    )
    if not supported:
        raise DomainError(
            "invalid",
            f"This template covers adults, {'/'.join(template['supportedGoals']).lower()}, "
            f"{template['minDaysPerWeek']}-{template['maxDaysPerWeek']} days, "
            f"and sessions of at least {template['minSessionMinutes']} minutes.",
        )


def _eligible_accessory(profile: JSON, library: JSON, accessory: JSON) -> JSON | None:
    """The template's optional accessory, if the session is long enough and the athlete can do it."""
    exercise = next((e for e in library["exercises"] if e["id"] == accessory["exerciseID"]), None)
    usable = (
        exercise is not None
        and is_enabled(exercise["review"], library)
        and profile["minutes"] >= accessory["minSessionMinutes"]
        and accessory["equipmentKind"] in profile["equipment"]
        and accessory["exerciseID"] not in profile["excludedExercises"]
    )
    return exercise if usable else None
