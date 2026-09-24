"""The Training Brain entry point: gate a request, then route it to a rule.

Gate order is the spec's §5.2 priority order and must not be reordered:

1. supported profile and an accepted plan
2. no active session (the pinned prescription cannot change mid-workout)
3. an enabled policy bundle
4. per-slot: reported pain → explicit exclusion → unreviewed exercise
5. evidence checks inside the individual rule
"""

from __future__ import annotations

from typing import Any

from ..athlete_state import has_active_session, next_plan
from ..content import exercises_by_id, is_enabled, policy_is_enabled
from ..errors import DomainError
from ..messages import Decision, decision
from .adaptation import propose_replan
from .adjustments import build_substitution, propose_reschedule, propose_shorter_session, propose_substitution
from .progression import propose_progression

JSON = dict[str, Any]


def decide(state: JSON, request: JSON, library: JSON, now: float) -> Decision:
    """Evaluate ``request`` against ``state`` and return a Decision (never mutates)."""
    profile = state.get("profile")
    plan = next_plan(state)
    if not profile or not profile["adultConfirmed"] or not profile["supportedScopeConfirmed"] or plan is None:
        return decision("PROFILE_REQUIRED")
    if has_active_session(state):
        return decision("SESSION_ACTIVE")
    if not policy_is_enabled(library):
        return decision("POLICY_NOT_APPROVED")

    kind = request["kind"]
    slot = _find_slot(plan, request.get("slotID"))

    if kind == "progression":
        if slot is None:
            return decision("SLOT_MISSING")
        blocked = slot_block(slot, state, profile, library)
        if blocked is not None:
            return blocked
        return propose_progression(state, plan, slot, library["policy"], now)

    if kind == "shorten":
        return propose_shorter_session(plan, request["minutes"])

    if kind == "substitute":
        ineligible = propose_substitution(state, plan, slot, request["alternativeID"], library, profile)
        if ineligible is not None:
            return ineligible
        assert slot is not None  # guaranteed by propose_substitution's eligibility check
        blocked = slot_block(slot, state, profile, library)
        if blocked is not None:
            return blocked
        alternative = exercises_by_id(library)[request["alternativeID"]]
        return build_substitution(plan, slot, alternative, profile["preferredUnit"])

    if kind == "reschedule":
        return propose_reschedule(plan, request["date"], now)

    if kind == "replan":
        return propose_replan(state, library, now)

    raise DomainError("unsupported")


def slot_block(slot: JSON, state: JSON, profile: JSON, library: JSON) -> Decision | None:
    """Priority-1 blocks for one slot, or ``None`` if guidance may proceed."""
    exercise_id = slot["exerciseID"]
    if exercise_id in state["painExclusions"]:
        return decision("REPORTED_PAIN")
    if exercise_id in profile["excludedExercises"]:
        return decision("EXERCISE_EXCLUDED")
    exercise = exercises_by_id(library).get(exercise_id)
    if exercise is None or not is_enabled(exercise["review"], library):
        return decision("UNREVIEWED_EXERCISE")
    return None


def _find_slot(plan: JSON, slot_id: str | None) -> JSON | None:
    return next((slot for slot in plan["slots"] if slot["id"] == slot_id), None)
