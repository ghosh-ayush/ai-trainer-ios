"""Changing the athlete's free days and minutes after onboarding (ADR-025).

The days chosen at onboarding are a starting point, not a contract. At any time the athlete can
name new free days (and minutes); the weekly planner (ADR-017) builds the weeks that fit, inside
the same research bounds, and the one the athlete picked is proposed. Nothing changes until the
athlete accepts it, and acceptance re-evaluates the request (rule 3).

Confirmed working loads carry over to the new week for the same exercise on the same equipment
(``carry_confirmed_loads``): they are the athlete's own values, not estimates.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..athlete_state import comparison_key
from ..errors import require
from ..messages import Decision, decision
from ..wording import WEEKDAY_NAMES, join_words
from .week_plans import DAYS_PER_WEEK
from .week_program import option_summaries, program_from_options, week_options

JSON = dict[str, Any]

# The same range onboarding offers for minutes per session.
MINUTES_BOUNDS = (15, 120)


def new_days_profile(profile: JSON, request: JSON) -> JSON:
    """``profile`` with the requested free days and, when given, minutes per session."""
    changed = dict(profile)
    changed["freeDays"] = sorted(set(request.get("freeDays") or []))
    changed["daysPerWeek"] = max(1, len(changed["freeDays"]))
    if request.get("minutes") is not None:
        changed["minutes"] = request["minutes"]
    return changed


def propose_new_days(state: JSON, library: JSON, request: JSON) -> Decision:
    """The week the athlete chose for their new free days, as a proposal; or what is missing."""
    if "planner" not in library:
        return decision("REPLAN_UNAVAILABLE")
    days = request.get("freeDays") or []
    if not days:
        return decision("DAYS_REQUIRED")
    require(all(isinstance(day, int) and 0 <= day < DAYS_PER_WEEK for day in days), "invalid", "Weekdays are 0 to 6.")
    minutes = request.get("minutes")
    low, high = MINUTES_BOUNDS
    require(minutes is None or low <= minutes <= high, "invalid", f"Choose between {low} and {high} minutes.")

    profile = state["profile"]
    changed = new_days_profile(profile, request)
    same_days = changed["freeDays"] == sorted(set(profile.get("freeDays") or []))
    if same_days and changed["minutes"] == profile["minutes"] and request.get("optionID") is None:
        return decision("SAME_DAYS")
    options = week_options(changed, library)
    if not options:
        return decision("NO_WEEK_FOR_DAYS")
    option_id = request.get("optionID")
    chosen = (
        options[0] if option_id is None else next((option for option in options if option["id"] == option_id), None)
    )
    if chosen is None:
        return decision("WEEK_OPTION_MISSING")
    week = option_summaries([chosen], library)[0]
    return decision("NEW_FREE_DAYS", explanation=_explanation(changed, week), week=week)


def new_days_program(state: JSON, library: JSON, request: JSON, week_id: str, now: float, ids: Iterable[str]) -> JSON:
    """The Program for an accepted change of free days, built from the same inputs as the proposal."""
    changed = new_days_profile(state["profile"], request)
    program = program_from_options(week_options(changed, library), week_id, changed, library, now, ids)
    return carry_confirmed_loads(program, state.get("program"))


def carry_confirmed_loads(program: JSON, previous: JSON | None) -> JSON:
    """Copy each confirmed working load and equipment steps from ``previous`` onto the same exercise.

    A slot matches when its comparison identity is the same (exercise, equipment, unit, basis and
    protocol), so evidence stays comparable. A load the athlete never confirmed stays unknown.
    """
    if not previous:
        return program
    confirmed: dict[str, JSON] = {}
    for plan in previous["plans"]:
        for slot in plan["slots"]:
            if slot.get("load") is not None:
                confirmed.setdefault(comparison_key(slot), slot)
    for plan in program["plans"]:
        for slot in plan["slots"]:
            known = confirmed.get(comparison_key(slot))
            if known is None:
                continue
            slot["load"] = known["load"]
            slot["equipment"]["availableLoads"] = list(known["equipment"].get("availableLoads", []))
    return program


def _explanation(profile: JSON, week: JSON) -> str:
    days = join_words([WEEKDAY_NAMES[day] for day in profile["freeDays"]])
    sessions = week["sessionsPerWeek"]
    return (
        f"A week for {days} at {profile['minutes']} minutes: {week['name']}, {sessions} session"
        f"{'s' if sessions != 1 else ''} a week. Loads you confirmed carry over. Nothing changes until you accept."
    )
