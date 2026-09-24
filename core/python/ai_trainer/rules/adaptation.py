"""Adapting the week to what the athlete actually does (ADR-018).

When the athlete keeps completing fewer sessions than their week plans, the core proposes a week
that fits what they have been doing. It uses the same planner (ADR-017), with the session count
capped at their recent completed sessions per week and the ranking told that history. Like
every change it is a Recommendation: nothing changes until the athlete accepts (rule 3), and
acceptance rebuilds the same week or refuses.

Only logged sessions count. A completed or ended-early session is done; a skipped session, or a
week with nothing logged, is not. No sensor, calendar or HealthKit data is read (rule 4). The
thresholds (window, how long a new week runs before it is judged, how many missed sessions a
week trigger a proposal) are the bundle's ``planner.adaptation`` owner decisions (rule 1).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from ..messages import Decision, decision
from .week_program import option_summaries, program_from_options, week_options

JSON = dict[str, Any]

DAY = 86400.0
WEEK = 7 * DAY
DONE_STATUSES = ("completed", "endedEarly")


def attendance(state: JSON, now: float, window_days: float) -> JSON | None:
    """Planned vs completed sessions a week since the later of the window start and the plan's acceptance.

    ``None`` without a program. ``weeks`` is how long the week has been followed within the window.
    The window ends at the end of the current day, so a proposal made this morning is still the
    identical decision when it is accepted this evening.
    """
    program = state.get("program")
    profile = state.get("profile")
    if not program or not profile:
        return None
    end = _end_of_day(now)
    start = max(end - window_days * DAY, program["acceptedAt"])
    weeks = max((end - start) / WEEK, 0.0)
    done = [
        session
        for session in state["sessions"]
        if session["status"] in DONE_STATUSES and start <= session["startedAt"] <= end
    ]
    return {
        "weeks": weeks,
        "planned": planned_sessions_per_week(program, profile),
        "done": len(done),
        "donePerWeek": len(done) / weeks if weeks > 0 else 0.0,
    }


def planned_sessions_per_week(program: JSON, profile: JSON) -> int:
    """A weekly plan has one session per plan; the one-session template repeats ``daysPerWeek`` times."""
    plans: list[JSON] = program["plans"]
    if any(plan.get("weekday") is not None for plan in plans):
        return len(plans)
    days: int = profile["daysPerWeek"]
    return days


def replan_due(state: JSON, library: JSON, now: float) -> bool:
    """The cheap check behind Today's ``autoReplan``: old enough to judge, and short of the plan."""
    planner = library.get("planner")
    program = state.get("program")
    if planner is None or not program:
        return False
    rules = planner["adaptation"]
    if _end_of_day(now) - program["acceptedAt"] < rules["minimumPlanAgeDays"] * DAY:
        return False
    summary = attendance(state, now, rules["windowDays"])
    return summary is not None and _short_of_plan(summary, rules)


def propose_replan(state: JSON, library: JSON, now: float) -> Decision:
    """A week fitted to recent attendance, as a proposal; or why the current week stays."""
    planner = library.get("planner")
    if planner is None:
        return decision("REPLAN_UNAVAILABLE")
    rules = planner["adaptation"]
    program = state["program"]
    summary = attendance(state, now, rules["windowDays"])
    if summary is None or _end_of_day(now) - program["acceptedAt"] < rules["minimumPlanAgeDays"] * DAY:
        return decision("REPLAN_NEEDS_HISTORY")
    if not _short_of_plan(summary, rules):
        return decision("FOLLOWING_THE_PLAN")
    options = _fitted_options(state, library, summary)
    if not options or _same_shape(options[0], program):
        return decision("NO_BETTER_WEEK")
    week = option_summaries(options[:1], library)[0]
    return decision("ADHERENCE_REPLAN", explanation=_explanation(summary, week), week=week)


def replan_program(state: JSON, library: JSON, now: float, ids: Iterable[str], option_id: str) -> JSON:
    """The Program for an accepted replan, rebuilt from the same attendance and inputs."""
    summary = attendance(state, now, library["planner"]["adaptation"]["windowDays"])
    assert summary is not None
    options = _fitted_options(state, library, summary)
    return program_from_options(options, option_id, state["profile"], library, now, ids)


def _end_of_day(now: float) -> float:
    """The end of the current day in the core's reference seconds (day boundaries at 00:00 UTC)."""
    return (math.floor(now / DAY) + 1) * DAY


def _short_of_plan(summary: JSON, rules: JSON) -> bool:
    missed: float = summary["planned"] - summary["donePerWeek"]
    threshold: float = rules["missedSessionsPerWeek"]
    return missed >= threshold


def _fitted_options(state: JSON, library: JSON, summary: JSON) -> list[JSON]:
    """The planner's options with sessions capped at what the athlete has been completing (at least one)."""
    cap = max(1, math.floor(summary["donePerWeek"] + 0.5))
    return week_options(state["profile"], library, session_cap=cap, recent_sessions_per_week=summary["donePerWeek"])


def _same_shape(option: JSON, program: JSON) -> bool:
    """Whether the best fitted week is the one the athlete already has (same split and session count)."""
    current_split = str(program["templateID"]).split(":", 1)[0]
    return option["split"] == current_split and len(option["sessions"]) == len(program["plans"])


def _explanation(summary: JSON, week: JSON) -> str:
    weeks = max(1, math.floor(summary["weeks"] + 0.5))
    done = summary["donePerWeek"]
    done_text = f"{done:.1f}".rstrip("0").rstrip(".")
    days = week["sessionsPerWeek"]
    return (
        f"Over the last {weeks} week{'s' if weeks != 1 else ''} you completed about {done_text} of "
        f"{summary['planned']} planned sessions a week. {week['name']} on {days} day{'s' if days != 1 else ''} "
        "fits what you have been doing and keeps each muscle's weekly work where your time allows."
    )
