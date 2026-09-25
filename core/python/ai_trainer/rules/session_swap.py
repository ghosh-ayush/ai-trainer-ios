"""Doing a different session today (ADR-026).

The athlete may pick another session of the week instead of the next one ("legs today instead").
The choice is proposed, and accepting swaps the two sessions: the chosen one becomes today's, and
the one it replaces moves to the chosen session's weekday, so the week keeps all its sessions.

Before the athlete accepts, the proposal says how recently the session's muscles were trained,
from logged sets only (rule 4), in two ways the owner chose:

- **The planner's back-to-back limit** (cited, ``consecutiveDayCap``): a muscle trained yesterday
  or earlier today should get at most that many sets. Going over is a warning.
- **A 72-hour notice** (``recoveryNoticeHours``, the app's own rule): any muscle trained in that
  window is listed, labelled as having no study behind it. It informs; it never blocks.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from ..athlete_state import next_plan
from ..content import exercises_by_id
from ..messages import Decision, decision
from ..wording import WEEKDAY_NAMES, join_words

JSON = dict[str, Any]

DAY = 86400.0
HOUR = 3600.0
COUNTED_KINDS = ("working", "extra")


def propose_session_swap(state: JSON, library: JSON, request: JSON, now: float) -> Decision:
    """The chosen session for today, as a proposal with its recovery notes; or why not."""
    plan = next_plan(state)
    assert plan is not None  # decide checked it
    if plan["modified"]:
        return decision("TEMPORARY_CHANGE_ACTIVE")
    plans: list[JSON] = state["program"]["plans"]
    chosen = next((candidate for candidate in plans if candidate["id"] == request["planID"]), None)
    if chosen is None:
        return decision("SESSION_MISSING")
    if chosen["id"] == plan["id"]:
        return decision("ALREADY_NEXT")
    lines = [_swap_sentence(plan, chosen)]
    lines.extend(recovery_notes(state, library, chosen, now, request.get("utcOffset")))
    lines.append("Nothing changes until you accept.")
    return decision("SESSION_SWAP", after=deepcopy(chosen), explanation=" ".join(lines))


def swapped_program(program: JSON, next_id: str, chosen_id: str) -> JSON:
    """``program`` with the next session and the chosen one trading places and weekdays."""
    swapped = deepcopy(program)
    plans: list[JSON] = swapped["plans"]
    first = next(index for index, plan in enumerate(plans) if plan["id"] == next_id)
    second = next(index for index, plan in enumerate(plans) if plan["id"] == chosen_id)
    first_day, second_day = plans[first].get("weekday"), plans[second].get("weekday")
    plans[first], plans[second] = plans[second], plans[first]
    for index, weekday in ((first, first_day), (second, second_day)):
        plans[index]["revision"] += 1
        if weekday is None:
            plans[index].pop("weekday", None)
        else:
            plans[index]["weekday"] = weekday
    return swapped


def recovery_notes(state: JSON, library: JSON, chosen: JSON, now: float, utc_offset: int | None) -> list[str]:
    """What the chosen session would ask of muscles trained recently: warnings, then the notice."""
    planner = library.get("planner")
    if planner is None:
        return []
    credits = _credits_by_exercise(library)
    session_sets = _session_sets(chosen, credits)
    notes: list[str] = []
    weekly = planner["weekly"]
    cap = weekly["consecutiveDayCap"]
    since_yesterday = _logged_sets(state, credits, _start_of_yesterday(now, utc_offset), now)
    over = [
        f"{muscle} ({_sets(session_sets[muscle])} sets)"
        for muscle in session_sets
        if since_yesterday.get(muscle, 0) > 0 and session_sets[muscle] > cap
    ]
    if over:
        notes.append(
            f"Heads-up: {join_words(over)} {'was' if len(over) == 1 else 'were'} trained yesterday or earlier today, "
            f"and this session goes over the planner's limit of {_sets(cap)} sets for a muscle on the day after "
            "it was trained."
        )
    hours = weekly.get("recoveryNoticeHours")
    if hours:
        recent = _last_trained(state, credits, now - hours * HOUR, now)
        listed = [
            f"{muscle} ({math.floor((now - recent[muscle]) / HOUR)} h ago)"
            for muscle in session_sets
            if muscle in recent
        ]
        if listed:
            notes.append(
                f"Trained in the last {_sets(hours)} hours: {join_words(listed)}. "
                f"{_sets(hours)} hours is the app's own notice; no study shows that long a rest is needed."
            )
    return notes


def _swap_sentence(plan: JSON, chosen: JSON) -> str:
    if chosen.get("weekday") is None:
        return f"Do {chosen['name']} today instead of {plan['name']}, which comes next after it."
    return f"Do {chosen['name']} today; {plan['name']} moves to {WEEKDAY_NAMES[chosen['weekday']]}."


def _credits_by_exercise(library: JSON) -> dict[str, dict[str, float]]:
    """Exercise id -> muscle credits of its planner role, as the weekly planner counts them."""
    roles = library["planner"]["structures"]["roles"]
    return {
        exercise_id: roles[exercise["role"]]["muscles"]
        for exercise_id, exercise in exercises_by_id(library).items()
        if exercise["role"] in roles
    }


def _session_sets(plan: JSON, credits: dict[str, dict[str, float]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for slot in plan["slots"]:
        for muscle, credit in credits.get(slot["exerciseID"], {}).items():
            totals[muscle] = totals.get(muscle, 0.0) + slot["workingSets"] * credit
    return totals


def _logged(
    state: JSON, credits: dict[str, dict[str, float]], start: float, end: float
) -> list[tuple[str, float, float]]:
    """``(muscle, credited sets, time)`` for every counted set logged in ``[start, end]``."""
    found: list[tuple[str, float, float]] = []
    for session in state["sessions"]:
        exercise_by_slot = {slot["id"]: slot["exerciseID"] for slot in session["plan"]["slots"]}
        for log in session["logs"]:
            if log["kind"] not in COUNTED_KINDS or log["reps"] < 1 or not start <= log["occurredAt"] <= end:
                continue
            for muscle, credit in credits.get(exercise_by_slot.get(log["prescriptionID"], ""), {}).items():
                found.append((muscle, credit, log["occurredAt"]))
    return found


def _logged_sets(state: JSON, credits: dict[str, dict[str, float]], start: float, end: float) -> dict[str, float]:
    totals: dict[str, float] = {}
    for muscle, credit, _ in _logged(state, credits, start, end):
        totals[muscle] = totals.get(muscle, 0.0) + credit
    return totals


def _last_trained(state: JSON, credits: dict[str, dict[str, float]], start: float, end: float) -> dict[str, float]:
    latest: dict[str, float] = {}
    for muscle, _, occurred_at in _logged(state, credits, start, end):
        latest[muscle] = max(latest.get(muscle, occurred_at), occurred_at)
    return latest


def _start_of_yesterday(now: float, utc_offset: int | None) -> float:
    """Local midnight at the start of yesterday (UTC when the host sent no offset)."""
    offset = utc_offset or 0
    return math.floor((now + offset) / DAY) * DAY - offset - DAY


def _sets(value: float) -> str:
    return f"{value:g}"
