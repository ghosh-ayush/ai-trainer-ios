"""TB-01: initial program selection.

Today there is exactly one repeating full-body template built from the
library's fixture exercises. Reviewed multi-day templates arrive with the
evidence-based content bundle (Track C) and will replace the constants below.
"""

from __future__ import annotations

from typing import Any

from ..athlete_state import equipment_context
from ..content import is_enabled, policy_is_enabled
from ..errors import DomainError

JSON = dict[str, Any]

SUPPORTED_GOALS = ("Hypertrophy", "Strength")
MIN_DAYS, MAX_DAYS = 2, 4
MIN_SESSION_MINUTES = 41
OPTIONAL_SLOT_MINUTES = 53
REQUIRED_ROLES = ("press", "pull", "squat")
OPTIONAL_ACCESSORY_ID = "db_curl"

FIXTURE_TEMPLATE_ID = "FULL_BODY_FIXTURE_01"
FIXTURE_LIBRARY_VERSION = "fixture-1"
FIXTURE_PLAN_NAME = "Full body - development fixture"
WARM_UP_MINUTES = 5

# IDs the host must supply: program, plan, then up to four slots.
REQUIRED_ID_COUNT = 6


def initial_program(profile: JSON, library: JSON, now: float, ids: list[str]) -> JSON:
    """Build the initial Program for ``profile`` or raise ``DomainError``.

    ``ids[0]`` is the program id, ``ids[1]`` the plan id, ``ids[2:]`` slot ids.
    """
    if not library["permitsFixtures"] or not policy_is_enabled(library):
        raise DomainError("unsupported")
    _require_supported_profile(profile)

    selected: list[tuple[JSON, bool]] = []
    for role in REQUIRED_ROLES:
        exercise = _first_eligible_exercise(role, profile, library)
        if exercise is None:
            raise DomainError("unsupported")
        selected.append((exercise, False))

    accessory = next((e for e in library["exercises"] if e["id"] == OPTIONAL_ACCESSORY_ID), None)
    include_accessory = (
        profile["minutes"] >= OPTIONAL_SLOT_MINUTES
        and "dumbbell" in profile["equipment"]
        and OPTIONAL_ACCESSORY_ID not in profile["excludedExercises"]
        and accessory is not None
    )
    if include_accessory:
        assert accessory is not None
        selected.append((accessory, True))

    slots = [
        _fixture_slot(ids[index + 2], exercise, profile["preferredUnit"], optional)
        for index, (exercise, optional) in enumerate(selected)
    ]
    plan = {
        "id": ids[1],
        "revision": 1,
        "name": FIXTURE_PLAN_NAME,
        "slots": slots,
        "modified": False,
        "warmUpMinutes": WARM_UP_MINUTES,
    }
    return {
        "id": ids[0],
        "revision": 1,
        "templateID": FIXTURE_TEMPLATE_ID,
        "libraryVersion": FIXTURE_LIBRARY_VERSION,
        "plans": [plan],
        "sequenceIndex": 0,
        "acceptedAt": now,
    }


def _fixture_slot(slot_id: str, exercise: JSON, unit: str, optional: bool) -> JSON:
    """One DP_TEST_01 prescription slot — test data, not an approved prescription."""
    return {
        "id": slot_id,
        "exerciseID": exercise["id"],
        "equipment": equipment_context(exercise, unit),
        "protocolID": "DP_TEST_01",
        "workingSets": 3,
        "lowerReps": 8,
        "upperReps": 10,
        "targets": [8, 8, 8],
        "restSeconds": 120,
        "optional": optional,
        "estimatedMinutes": 12,
    }


def _require_supported_profile(profile: JSON) -> None:
    supported = (
        profile["adultConfirmed"]
        and profile["supportedScopeConfirmed"]
        and profile["goal"] in SUPPORTED_GOALS
        and MIN_DAYS <= profile["daysPerWeek"] <= MAX_DAYS
        and profile["minutes"] >= MIN_SESSION_MINUTES
    )
    if not supported:
        raise DomainError(
            "invalid",
            "This fixture covers adults, strength/hypertrophy, 2-4 days, and sessions of at least 41 minutes.",
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
