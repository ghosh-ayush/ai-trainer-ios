"""Read-only accessors and small derived values over the AthleteState record.

Everything here is pure: no clock, no IDs, no mutation. Mutations live in
``commands/`` and ``recommendations.py``.
"""

from __future__ import annotations

from typing import Any

JSON = dict[str, Any]

ACTIVE_STATUSES = ("inProgress", "paused")


def is_active(session: JSON) -> bool:
    """A session is active while it is in progress or paused."""
    status: str = session["status"]
    return status in ACTIVE_STATUSES


def active_session(state: JSON) -> JSON | None:
    """The most recent active session, if any."""
    sessions: list[JSON] = state["sessions"]
    for session in reversed(sessions):
        if is_active(session):
            return session
    return None


def has_active_session(state: JSON) -> bool:
    return active_session(state) is not None


def next_plan(state: JSON) -> JSON | None:
    """The plan the athlete will train next.

    A temporary override (shortened/substituted session) wins over the
    program's sequenced plan.
    """
    override: JSON | None = state.get("nextPlanOverride")
    if override is not None:
        return override
    program: JSON | None = state.get("program")
    if not program:
        return None
    index: int = program["sequenceIndex"]
    plans: list[JSON] = program["plans"]
    if 0 <= index < len(plans):
        return plans[index]
    return None


def comparison_key(slot: JSON) -> str:
    """Identity of a prescription for evidence comparison.

    Performance is only comparable when exercise, equipment identity, unit,
    load basis, protocol and rep convention all match.
    """
    equipment = slot["equipment"]
    return "|".join(
        (
            slot["exerciseID"],
            equipment["id"],
            equipment["unit"],
            equipment["basis"],
            slot["protocolID"],
            "bilateral-repetition",
        )
    )


def estimated_minutes(plan: JSON) -> int:
    """Warm-up plus the sum of every slot's estimate."""
    total: int = plan["warmUpMinutes"] + sum(slot["estimatedMinutes"] for slot in plan["slots"])
    return total


def equipment_context(exercise: JSON, unit: str) -> JSON:
    """A fresh, unconfigured equipment record for ``exercise``.

    ``availableLoads`` starts empty: the athlete confirms their own steps.
    """
    return {
        "id": "local-" + exercise["id"],
        "name": "My " + exercise["name"] + " equipment",
        "kind": exercise["equipmentKind"],
        "unit": unit,
        "basis": exercise["basis"],
        "availableLoads": [],
    }


def has_working_set(session: JSON, slot_id: str, index: int) -> bool:
    """Whether working set ``index`` of ``slot_id`` has already been logged."""
    return any(
        log["prescriptionID"] == slot_id and log["index"] == index and log["kind"] == "working"
        for log in session["logs"]
    )


def plan_contains_excluded_exercise(state: JSON, plan: JSON) -> bool:
    """True if any slot is under a pain exclusion or an explicit user exclusion."""
    profile = state.get("profile") or {}
    user_exclusions = profile.get("excludedExercises", [])
    return any(
        slot["exerciseID"] in state["painExclusions"] or slot["exerciseID"] in user_exclusions for slot in plan["slots"]
    )
