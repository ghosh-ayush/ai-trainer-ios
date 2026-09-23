"""TB-01: initial program selection.

The program is built from the content bundle's ``template``: one repeating
full-body session with one exercise per required role and an optional
accessory. Every number (sets, reps, rest, minutes) comes from the template;
none is defined here. Reviewed multi-day templates arrive with the
evidence-based content bundle (Track C).
"""

from __future__ import annotations

from typing import Any

from ..athlete_state import equipment_context
from ..content import is_enabled, policy_is_enabled
from ..errors import DomainError

JSON = dict[str, Any]

# IDs the host must supply: program, plan, then up to four slots.
REQUIRED_ID_COUNT = 6


def initial_program(profile: JSON, library: JSON, now: float, ids: list[str]) -> JSON:
    """Build the initial Program for ``profile`` or raise ``DomainError``.

    ``ids[0]`` is the program id, ``ids[1]`` the plan id, ``ids[2:]`` slot ids.
    """
    if not library["permitsFixtures"] or not policy_is_enabled(library):
        raise DomainError("unsupported")
    template = library["template"]
    _require_supported_profile(profile, template)

    selected: list[tuple[JSON, bool]] = []
    for role in template["requiredRoles"]:
        exercise = _first_eligible_exercise(role, profile, library)
        if exercise is None:
            raise DomainError("unsupported")
        selected.append((exercise, False))

    accessory = _eligible_accessory(profile, library, template["accessory"])
    if accessory is not None:
        selected.append((accessory, True))

    slots = [
        _slot(ids[index + 2], exercise, profile["preferredUnit"], optional, template["slot"])
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


def _first_eligible_exercise(role: str, profile: JSON, library: JSON) -> JSON | None:
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
