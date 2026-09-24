"""Weekly programs for 1-7 free days (ADR-017): distinct options, and the Program they become.

``week_plans`` lists the weeks the evidence allows and ``plan_ranking`` orders them. This module
feeds both from the athlete's profile and the content bundle's ``planner`` section, keeps a few
genuinely different options to show (a different split or session count each), and turns the
chosen one into a Program with one plan per session.

Reps, rest and protocol come from the template's cited per-goal prescription. The sets per
exercise come from the week itself. The working load starts unknown, as in the one-session
template: nothing is estimated.

When the athlete gave free weekdays, only those days are used. When they gave only a number of
days, every weekday is open and the plan uses at most that many; the days shown are a
suggestion the athlete sees before accepting, never a stored fact about them.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from typing import Any

from ..athlete_state import equipment_context
from ..errors import DomainError, require
from .plan_ranking import rank_weeks
from .selection import first_eligible_exercise, prescription
from .week_plans import DAYS_PER_WEEK, week_candidates

JSON = dict[str, Any]


def week_options(profile: JSON, library: JSON, adjust: JSON | None = None) -> list[JSON]:
    """The distinct weeks to show this athlete, best first (at most the bundle's ``optionsShown``).

    ``adjust`` fits a replan to what the athlete has been doing (ADR-018); a first plan has none,
    so a preview and its acceptance stay identical. Its optional keys:

    - ``sessionCap`` / ``minSessions``: bounds on sessions a week;
    - ``extraDays``: weekdays the athlete has been training on, added to their free days;
    - ``minutesCap``: session minutes no longer than this on any day;
    - ``recentSessionsPerWeek`` and ``habitDays``: history for the ranking.
    """
    adjust = adjust or {}
    planner = library["planner"]
    weekly = _weekly_for_goal(planner["weekly"], profile["goal"])
    structures = planner["structures"]
    target = _target(planner, profile)
    days, max_sessions = _free_days(profile)
    if adjust.get("extraDays"):
        days = sorted(set(days) | set(adjust["extraDays"]))
    if adjust.get("sessionCap") is not None:
        cap: int = adjust["sessionCap"]
        max_sessions = min(max_sessions or cap, cap)
    minutes_by_day = _minutes_by_day(profile, days)
    if adjust.get("minutesCap") is not None:
        minutes_by_day = {day: min(minutes, adjust["minutesCap"]) for day, minutes in minutes_by_day.items()}
    candidates = week_candidates(
        days,
        minutes_by_day,
        weekly,
        structures,
        target,
        available_roles(profile, library),
        max_sessions,
        adjust.get("minSessions", 1),
    )
    athlete = {
        "goal": profile["goal"],
        "target": target,
        "recentSessionsPerWeek": adjust.get("recentSessionsPerWeek"),
        "habitDays": adjust.get("habitDays"),
    }
    ranked = rank_weeks(candidates, athlete, weekly, structures, planner["ranking"])
    return distinct_options(ranked, planner["ranking"]["optionsShown"])


def option_summaries(options: list[JSON], library: JSON) -> list[JSON]:
    """The ``WeekOption`` records the host shows: days, sessions, minutes, volume and reasons."""
    structures = library["planner"]["structures"]
    summaries: list[JSON] = []
    for option in options:
        sessions = [
            {
                "weekday": session["day"],
                "name": structures["sessions"][session["type"]]["name"],
                "minutes": session["minutes"],
                "exercises": len(session["slots"]),
                "sets": sum(slot["sets"] for slot in session["slots"]),
            }
            for session in option["sessions"]
        ]
        summaries.append(
            {
                "id": option["id"],
                "split": option["split"],
                "name": structures["splitNames"][option["split"]],
                "days": option["days"],
                "sessions": sessions,
                "sessionsPerWeek": len(sessions),
                "weeklyMinutes": sum(session["minutes"] for session in sessions),
                "volume": option["volume"],
                "score": option["score"],
                "reasons": option["reasons"],
            }
        )
    return summaries


def week_program(profile: JSON, library: JSON, now: float, ids: Iterable[str], option_id: str | None) -> JSON:
    """The Program for ``option_id`` (the best option when ``None``); one plan per session.

    The options are rebuilt from the same inputs, so accepting re-evaluates the choice: an
    option that no longer fits is refused rather than applied (rule 3). ``ids`` are consumed
    lazily, one for the program and one per plan and slot, so a command keeps the rest.
    """
    return program_from_options(week_options(profile, library), option_id, profile, library, now, ids)


def program_from_options(
    options: list[JSON], option_id: str | None, profile: JSON, library: JSON, now: float, ids: Iterable[str]
) -> JSON:
    """The Program for the option named ``option_id`` among ``options`` (the first when ``None``)."""
    require(bool(options), "invalid", "No week fits these days and minutes. Add a free day or more time.")
    if option_id is None:
        chosen = options[0]
    else:
        match = next((option for option in options if option["id"] == option_id), None)
        require(
            match is not None, "invalid", "That week no longer fits your days and minutes. Review the options again."
        )
        assert match is not None
        chosen = match
    planner = library["planner"]
    weekly = _weekly_for_goal(planner["weekly"], profile["goal"])
    structures = planner["structures"]
    rx = prescription(library["template"], profile["goal"])
    supply = iter(ids)
    program_id = _take(supply)
    plans = []
    for session in chosen["sessions"]:
        definition = structures["sessions"][session["type"]]
        plan_id = _take(supply)
        slots = [
            _slot(_take(supply), slot, definition, profile, library, rx, weekly["minutesPerSet"])
            for slot in session["slots"]
        ]
        plans.append(
            {
                "id": plan_id,
                "revision": 1,
                "name": definition["name"],
                "slots": slots,
                "modified": False,
                "warmUpMinutes": weekly["warmUpMinutes"],
                "weekday": session["day"],
            }
        )
    return {
        "id": program_id,
        "revision": 1,
        "templateID": chosen["id"],
        "libraryVersion": library["policy"]["version"],
        "plans": plans,
        "sequenceIndex": 0,
        "acceptedAt": now,
    }


def available_roles(profile: JSON, library: JSON) -> set[str]:
    """Roles with at least one exercise this athlete can do (equipment, exclusions, review)."""
    roles = library["planner"]["structures"]["roles"]
    return {role for role in roles if first_eligible_exercise(role, profile, library) is not None}


def distinct_options(ranked: list[JSON], count: int) -> list[JSON]:
    """The best week for each split and session count, in rank order, up to ``count``.

    Two weeks with the same split and number of sessions differ only in which days they use,
    so only the higher-ranked one is offered.
    """
    chosen: list[JSON] = []
    seen: set[tuple[str, int]] = set()
    for option in ranked:
        shape = (option["split"], len(option["sessions"]))
        if shape in seen:
            continue
        seen.add(shape)
        chosen.append(option)
        if len(chosen) == count:
            break
    return chosen


def _take(supply: Iterator[str]) -> str:
    """The next host-supplied id; running out is a contract error, never a generated id."""
    try:
        return next(supply)
    except StopIteration as exhausted:
        raise DomainError("invalid", "Not enough ids for this week.") from exhausted


def _slot(
    slot_id: str,
    week_slot: JSON,
    definition: JSON,
    profile: JSON,
    library: JSON,
    rx: JSON,
    minutes_per_set: float,
) -> JSON:
    """One prescription slot: the role's exercise, the week's sets, the goal's reps and rest."""
    exercise = first_eligible_exercise(week_slot["role"], profile, library)
    require(exercise is not None, "unsupported")
    assert exercise is not None
    sets = week_slot["sets"]
    return {
        "id": slot_id,
        "exerciseID": exercise["id"],
        "equipment": equipment_context(exercise, profile["preferredUnit"]),
        "protocolID": rx["protocolID"],
        "workingSets": sets,
        "lowerReps": rx["lowerReps"],
        "upperReps": rx["upperReps"],
        "targets": [rx["lowerReps"]] * sets,
        "restSeconds": rx["restSeconds"],
        "optional": week_slot["role"] not in definition["roles"],
        "estimatedMinutes": math.ceil(sets * minutes_per_set),
    }


def _weekly_for_goal(weekly: JSON, goal: str) -> JSON:
    """The guardrails with ``minutesPerSet`` narrowed to the athlete's goal (rest differs by goal)."""
    minutes: JSON = weekly["minutesPerSet"]
    if goal not in minutes:
        raise DomainError("invalid", f"The planner has no time per set for the goal {goal}.")
    return {**weekly, "minutesPerSet": minutes[goal]}


def _target(planner: JSON, profile: JSON) -> float:
    """Weekly working sets per major muscle to aim for, by goal and experience."""
    by_goal: JSON = planner["targets"].get(profile["goal"]) or {}
    target = by_goal.get(profile["experience"])
    if target is None:
        raise DomainError("invalid", "The planner has no weekly target for this goal and experience.")
    value: float = target
    return value


def _free_days(profile: JSON) -> tuple[list[int], int | None]:
    """The athlete's free weekdays, or every weekday capped at ``daysPerWeek`` when unknown."""
    free = profile.get("freeDays")
    if free:
        return sorted(set(free)), None
    require(1 <= profile["daysPerWeek"] <= DAYS_PER_WEEK, "invalid", "Choose between 1 and 7 days a week.")
    return list(range(DAYS_PER_WEEK)), profile["daysPerWeek"]


def _minutes_by_day(profile: JSON, days: list[int]) -> dict[int, int]:
    """Minutes per free day: the day's own value when given, else the athlete's usual minutes."""
    by_day: dict[str, int] = profile.get("minutesByDay") or {}
    usual: int = profile["minutes"]
    return {day: by_day.get(str(day), usual) for day in days}
