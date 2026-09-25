"""Adapting the week to what the athlete actually does (ADR-018).

The core compares the week the athlete accepted with the sessions they have logged, and proposes
a week that fits when their training has drifted from it in one of four ways:

- **fewer sessions** than planned, on average, by at least the bundle's threshold;
- sessions that **ended early for lack of time**, often enough to be a pattern;
- **more sessions** than planned, on average, by at least the threshold;
- training mostly on **other weekdays** than the plan uses.

The proposal uses the same planner (ADR-017), with its inputs fitted to that history: sessions
capped or raised to what the athlete completes, minutes capped at how long time-limited sessions
lasted, and the weekdays the athlete actually trains on added to their free days and preferred
by the ranking. Like every change it is a Recommendation: nothing changes until the athlete
accepts (rule 3), and acceptance rebuilds the same week or refuses.

Only logged sessions count. A completed or ended-early session is done; a skipped session, or a
week with nothing logged, is not. Durations come from the session's own start and end times,
which the athlete records by starting and finishing it; no sensor, calendar or HealthKit data is
read (rule 4). Weekdays need the athlete's UTC offset, which the host sends with the request;
without it, weekday habits stay unknown and are not used. Every threshold is a bundle
``planner.adaptation`` owner decision (rule 1).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from ..athlete_state import status_seconds
from ..messages import Decision, decision
from ..wording import WEEKDAY_SHORT, join_words
from .week_program import option_summaries, program_from_options, week_options

JSON = dict[str, Any]

DAY = 86400.0
WEEK = 7 * DAY
DONE_STATUSES = ("completed", "endedEarly")
MINUTE_STEP = 5


def attendance(state: JSON, now: float, window_days: float, utc_offset: int | None = None) -> JSON | None:
    """What the athlete did since the later of the window start and the plan's acceptance.

    ``None`` without a program. The window ends at the end of the current day, so a proposal made
    this morning is still the identical decision when it is accepted this evening. Keys:
    ``weeks``, ``planned`` (sessions a week), ``done``, ``donePerWeek``, ``timeLimitedMinutes``
    (how long each session that ended early for time lasted), and, when ``utc_offset`` is known,
    ``weekdayWeeks`` (weekday -> number of window weeks with a session on it).
    """
    program = state.get("program")
    profile = state.get("profile")
    if not program or not profile:
        return None
    end = _end_of_day(now)
    start = max(end - window_days * DAY, program["acceptedAt"])
    away = status_seconds(state, start, end)  # ADR-019: a break or illness is not a missed session
    weeks = max((end - start - away) / WEEK, 0.0)
    done = [
        session
        for session in state["sessions"]
        if session["status"] in DONE_STATUSES and start <= session["startedAt"] <= end
    ]
    time_limited = [
        (session["endedAt"] - session["startedAt"]) / 60
        for session in done
        if session["status"] == "endedEarly" and "time" in session["omissions"].values() and session.get("endedAt")
    ]
    summary: JSON = {
        "weeks": weeks,
        "activeDays": weeks * 7,
        "planned": planned_sessions_per_week(program, profile),
        "done": len(done),
        "donePerWeek": len(done) / weeks if weeks > 0 else 0.0,
        "timeLimitedMinutes": time_limited,
        "doneWeekdays": [],
        "weekdayWeeks": None,
    }
    if utc_offset is not None:
        weekday_weeks: dict[int, set[int]] = {}
        for session in done:
            day = local_weekday(session["startedAt"], utc_offset)
            summary["doneWeekdays"].append(day)
            weekday_weeks.setdefault(day, set()).add(math.floor((session["startedAt"] - start) / WEEK))
        summary["weekdayWeeks"] = {day: len(indexes) for day, indexes in weekday_weeks.items()}
    return summary


def local_weekday(moment: float, utc_offset: int) -> int:
    """Weekday 0-6 (Monday = 0) of a reference-epoch time at ``utc_offset`` seconds from UTC.

    The reference epoch, 2001-01-01 00:00 UTC, was a Monday.
    """
    return math.floor((moment + utc_offset) / DAY) % 7


def planned_sessions_per_week(program: JSON, profile: JSON) -> int:
    """A weekly plan has one session per plan; the one-session template repeats ``daysPerWeek`` times."""
    plans: list[JSON] = program["plans"]
    if any(plan.get("weekday") is not None for plan in plans):
        return len(plans)
    days: int = profile["daysPerWeek"]
    return days


def replan_due(state: JSON, library: JSON, now: float, utc_offset: int | None = None) -> bool:
    """The cheap check behind Today's ``autoReplan``: old enough to judge, and drifted from the plan."""
    planner = library.get("planner")
    program = state.get("program")
    if planner is None or not program:
        return False
    rules = planner["adaptation"]
    summary = attendance(state, now, rules["windowDays"], utc_offset)
    return summary is not None and _old_enough(summary, program, now, rules) and bool(_drift(summary, program, rules))


def propose_replan(state: JSON, library: JSON, now: float, utc_offset: int | None = None) -> Decision:
    """A week fitted to the athlete's recent training, as a proposal; or why the current week stays."""
    planner = library.get("planner")
    if planner is None:
        return decision("REPLAN_UNAVAILABLE")
    rules = planner["adaptation"]
    program = state["program"]
    summary = attendance(state, now, rules["windowDays"], utc_offset)
    if summary is None or not _old_enough(summary, program, now, rules):
        return decision("REPLAN_NEEDS_HISTORY")
    drift = _drift(summary, program, rules)
    if not drift:
        return decision("FOLLOWING_THE_PLAN")
    adjust = _adjustments(summary, drift, rules)
    options = week_options(state["profile"], library, adjust)
    if not options or _unchanged(options[0], program, adjust):
        return decision("NO_BETTER_WEEK")
    week = option_summaries(options[:1], library)[0]
    return decision(_reason(drift), explanation=_explanation(summary, drift, adjust, week), week=week)


def replan_program(
    state: JSON, library: JSON, now: float, ids: Iterable[str], option_id: str, utc_offset: int | None = None
) -> JSON:
    """The Program for an accepted replan, rebuilt from the same history and inputs."""
    rules = library["planner"]["adaptation"]
    summary = attendance(state, now, rules["windowDays"], utc_offset)
    assert summary is not None
    adjust = _adjustments(summary, _drift(summary, state["program"], rules), rules)
    options = week_options(state["profile"], library, adjust)
    return program_from_options(options, option_id, state["profile"], library, now, ids)


def _old_enough(summary: JSON, program: JSON, now: float, rules: JSON) -> bool:
    """The week has run long enough to judge, and enough of that time was not a break or illness."""
    minimum: float = rules["minimumPlanAgeDays"]
    age_ok = _end_of_day(now) - program["acceptedAt"] >= minimum * DAY
    active_days: float = summary["activeDays"]
    return age_ok and active_days >= minimum


def _drift(summary: JSON, program: JSON, rules: JSON) -> list[str]:
    """The ways the athlete's training has drifted from the week, in the order they are explained."""
    drift: list[str] = []
    missed: float = summary["planned"] - summary["donePerWeek"]
    fewer_threshold: float = rules["missedSessionsPerWeek"]
    more_threshold: float = rules["extraSessionsPerWeek"]
    if missed >= fewer_threshold:
        drift.append("fewer")
    if len(summary["timeLimitedMinutes"]) >= rules["endedEarlyForTime"]:
        drift.append("shorter")
    if -missed >= more_threshold:
        drift.append("more")
    if _trains_on_other_days(summary, program, rules):
        drift.append("days")
    return drift


def _trains_on_other_days(summary: JSON, program: JSON, rules: JSON) -> bool:
    """At least ``otherDaysShare`` of completed sessions fell on weekdays the plan does not use."""
    planned_days = {plan["weekday"] for plan in program["plans"] if plan.get("weekday") is not None}
    done_days: list[int] = summary["doneWeekdays"]
    if not planned_days or not done_days or not habit_days(summary, rules):
        return False
    elsewhere = sum(1 for day in done_days if day not in planned_days)
    share: float = rules["otherDaysShare"]
    return elsewhere / len(done_days) >= share


def habit_days(summary: JSON, rules: JSON) -> list[int]:
    """Weekdays the athlete trained on in at least ``habitShare`` of the window's weeks; empty when unknown."""
    weekday_weeks = summary.get("weekdayWeeks")
    if not weekday_weeks:
        return []
    weeks = max(1, math.floor(summary["weeks"] + 0.5))
    share: float = rules["habitShare"]
    return sorted(day for day, count in weekday_weeks.items() if count / weeks >= share)


def _adjustments(summary: JSON, drift: list[str], rules: JSON) -> JSON:
    """Planner inputs fitted to the drift: session bounds, extra days, a minutes cap and history."""
    done_per_week: float = summary["donePerWeek"]
    completed = max(1, math.floor(done_per_week + 0.5))
    habits = habit_days(summary, rules)
    adjust: JSON = {"recentSessionsPerWeek": done_per_week}
    if habits:
        adjust["habitDays"] = habits
        adjust["extraDays"] = habits
    if "fewer" in drift:
        adjust["sessionCap"] = completed
    if "more" in drift:
        adjust["minSessions"] = summary["planned"] + 1
        adjust["sessionCap"] = max(completed, summary["planned"] + 1)
    if "days" in drift and "fewer" not in drift and "more" not in drift:
        adjust["minSessions"] = summary["planned"]
        adjust["sessionCap"] = summary["planned"]
    if "shorter" in drift:
        adjust["minutesCap"] = _time_limited_minutes(summary, rules)
    return adjust


def _time_limited_minutes(summary: JSON, rules: JSON) -> int:
    """The median length of sessions that ended early for time, down to 5 minutes, never below the minimum."""
    lengths: list[float] = sorted(summary["timeLimitedMinutes"])
    middle = len(lengths) // 2
    median = lengths[middle] if len(lengths) % 2 else (lengths[middle - 1] + lengths[middle]) / 2
    floor_minutes: int = rules["minimumSessionMinutes"]
    return max(floor_minutes, math.floor(median / MINUTE_STEP) * MINUTE_STEP)


def _unchanged(option: JSON, program: JSON, adjust: JSON) -> bool:
    """Whether the best fitted week is the one the athlete already has, at the same length."""
    if option["id"] != program["templateID"]:
        return False
    cap = adjust.get("minutesCap")
    if cap is None:
        return True
    return all(
        plan["warmUpMinutes"] + sum(slot["estimatedMinutes"] for slot in plan["slots"]) <= cap
        for plan in program["plans"]
    )


def _reason(drift: list[str]) -> str:
    reasons = {
        "fewer": "ADHERENCE_REPLAN",
        "shorter": "SHORTER_SESSIONS_REPLAN",
        "more": "MORE_SESSIONS_REPLAN",
        "days": "TRAINING_DAYS_REPLAN",
    }
    return reasons[drift[0]]


def _explanation(summary: JSON, drift: list[str], adjust: JSON, week: JSON) -> str:
    """What the athlete did, then the week that fits it."""
    weeks = max(1, math.floor(summary["weeks"] + 0.5))
    period = f"Over the last {weeks} week{'s' if weeks != 1 else ''}"
    done = f"{summary['donePerWeek']:.1f}".rstrip("0").rstrip(".")
    sentences: list[str] = []
    if "fewer" in drift:
        sentences.append(f"{period} you completed about {done} of {summary['planned']} planned sessions a week.")
    if "more" in drift:
        sentences.append(
            f"{period} you completed about {done} sessions a week, more than the {summary['planned']} planned."
        )
    if "shorter" in drift:
        count = len(summary["timeLimitedMinutes"])
        sentences.append(f"{count} sessions ended early for time; they lasted about {adjust['minutesCap']} minutes.")
    if "days" in drift or adjust.get("habitDays"):
        names = join_words([WEEKDAY_SHORT[day] for day in adjust.get("habitDays", [])])
        if names:
            sentences.append(f"You have mostly trained on {names}.")
    days = week["sessionsPerWeek"]
    schedule = ", ".join(WEEKDAY_SHORT[session["weekday"]] for session in week["sessions"])
    sentences.append(
        f"{week['name']} on {days} day{'s' if days != 1 else ''} ({schedule}) fits what you have been doing "
        "and keeps each muscle's weekly work where your time allows."
    )
    return " ".join(sentences)


def _end_of_day(now: float) -> float:
    """The end of the current day in the core's reference seconds (day boundaries at 00:00 UTC)."""
    return (math.floor(now / DAY) + 1) * DAY
