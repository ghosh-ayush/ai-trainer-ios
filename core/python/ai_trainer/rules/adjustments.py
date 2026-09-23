"""Session-level adjustments the athlete can preview: shorten, substitute, reschedule.

All three return a *proposal* (``after`` plan) — nothing is applied here.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..athlete_state import equipment_context, estimated_minutes
from ..content import exercises_by_id, is_enabled
from ..messages import Decision, decision

JSON = dict[str, Any]


def propose_shorter_session(plan: JSON, available_minutes: int) -> Decision:
    """TB-03: drop optional slots (last first) until the session fits.

    Required work, warm-up and rest are never compressed.
    """
    if available_minutes <= 0:
        return decision("TIME_REQUIRED")
    proposed = deepcopy(plan)
    while estimated_minutes(proposed) > available_minutes:
        optional_index = _last_optional_slot_index(proposed)
        if optional_index is None:
            break
        proposed["slots"].pop(optional_index)
    if estimated_minutes(proposed) > available_minutes:
        return decision("REQUIRED_WORK_DOES_NOT_FIT")
    if proposed["slots"] == plan["slots"]:
        return decision("ALREADY_FITS")
    proposed["modified"] = True
    return decision("OPTIONAL_WORK_REMOVED", proposed)


def propose_substitution(
    state: JSON, plan: JSON, slot: JSON | None, alternative_id: str, library: JSON, profile: JSON
) -> Decision | None:
    """TB-06: swap a slot for a curated directional alternative.

    Returns ``None`` when the substitute is eligible and the caller should
    still run the slot-level gates; returns a Decision otherwise. The caller
    completes the proposal with :func:`build_substitution`.
    """
    exercises = exercises_by_id(library)
    alternative = exercises.get(alternative_id)
    original = exercises.get(slot["exerciseID"]) if slot else None
    eligible = (
        original is not None
        and alternative is not None
        and alternative["id"] in original["alternatives"]
        and is_enabled(alternative["review"], library)
        and alternative["equipmentKind"] in profile["equipment"]
        and alternative["id"] not in profile["excludedExercises"]
        and alternative["id"] not in state["painExclusions"]
    )
    if not eligible:
        return decision("NO_ELIGIBLE_SUBSTITUTE")
    return None


def build_substitution(plan: JSON, slot: JSON, alternative: JSON, unit: str) -> Decision:
    """The substitution proposal. Load is never transferred between equipment identities."""
    proposed = deepcopy(plan)
    target = next(candidate for candidate in proposed["slots"] if candidate["id"] == slot["id"])
    target.update(exerciseID=alternative["id"], equipment=equipment_context(alternative, unit))
    target.pop("load", None)
    proposed["modified"] = True
    explanation = (
        f"Use {alternative['name']} for this session only. "
        "Confirm its own load and equipment; the original load is not transferred."
    )
    return decision("CURATED_SUBSTITUTION", proposed, explanation=explanation)


def propose_reschedule(plan: JSON, date: float, now: float) -> Decision:
    """TB-02: move the next session without doubling work or reordering the sequence."""
    if date < now:
        return decision("DATE_IN_PAST")
    proposed = deepcopy(plan)
    proposed["scheduledDate"] = date
    return decision("USER_RESCHEDULE", proposed)


def _last_optional_slot_index(plan: JSON) -> int | None:
    for index in reversed(range(len(plan["slots"]))):
        if plan["slots"][index]["optional"]:
            return index
    return None
