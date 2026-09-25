"""Weekly plan candidates: every layout of the athlete's free days that the evidence allows.

The owner chose AI-chosen plans inside research bounds (ADR-017): there is no fixed
"N days -> split" table. This module builds the space of valid weeks. ``plan_ranking`` orders
them for one athlete, and the on-device model may pick among the top ones. No number here is
the module's own: every limit comes from the content bundle's ``weekly`` guardrails, each cited
there or recorded as an owner decision with a cited rationale
(docs/research/training-frequency-evidence.md).

A candidate is a list of sessions (weekday and session type), each with role slots and their
working sets, plus the weekly sets each muscle receives. A set counts fully for a role's primary
muscles and partly for its synergists, at the credit the bundle gives. A candidate is returned
only when it keeps every guardrail:

- each session fits the athlete's minutes that day, and each exercise gets between the minimum
  and maximum sets per exercise;
- no muscle goes above the weekly ceiling or the per-session cap;
- when two sessions that train a muscle fall on consecutive days (Sunday to Monday included),
  the later one gives that muscle no more than the consecutive-day cap;
- every major muscle that an available role can train reaches at least the time-limited floor.
  ``volume`` says whether the full weekly floor was reached (``full``) or only the time-limited
  one (``reduced``).
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any

from ..errors import DomainError
from ..wording import WEEKDAY_SHORT

JSON = dict[str, Any]

DAYS_PER_WEEK = 7


def week_candidates(
    free_days: list[int],
    minutes_by_day: dict[int, int],
    weekly: JSON,
    structures: JSON,
    target: float,
    available_roles: set[str],
    max_sessions: int | None = None,
    min_sessions: int = 1,
) -> list[JSON]:
    """Every week the guardrails allow on ``free_days``, in a stable order.

    ``free_days`` are weekdays 0-6 (Monday = 0) and ``minutes_by_day`` gives the session minutes
    the athlete has on each of them. ``target`` is the weekly working sets per major muscle to aim
    for, between the floor and the ceiling. Roles outside ``available_roles`` (no eligible
    exercise for this athlete) are left out of every session. ``max_sessions`` lowers the
    bundle's session maximum, for an athlete who said how many days but not which;
    ``min_sessions`` asks for at least that many (a replan for an athlete training more, ADR-018).
    """
    days = sorted(set(free_days))
    if not days or any(day not in range(DAYS_PER_WEEK) for day in days):
        raise DomainError("invalid", "Choose at least one free weekday.")
    if any(day not in minutes_by_day for day in days):
        raise DomainError("invalid", "Give the session minutes for every free day.")
    most_sessions = min(len(days), weekly["maxSessionsPerWeek"], max_sessions or DAYS_PER_WEEK)
    trainable = _trainable_major_muscles(structures, available_roles)

    candidates: list[JSON] = []
    seen: set[tuple[tuple[int, str], ...]] = set()
    for count in range(max(1, min_sessions), most_sessions + 1):
        for chosen in combinations(days, count):
            for split_id, cycle in structures["splits"].items():
                for offset in range(len(cycle)):
                    types = [cycle[(offset + index) % len(cycle)] for index in range(count)]
                    layout = tuple(zip(chosen, types, strict=True))
                    if layout in seen:
                        continue
                    seen.add(layout)
                    candidate = _build(split_id, layout, minutes_by_day, weekly, structures, target, available_roles)
                    if candidate is not None and _meets_floor(candidate, weekly, trainable):
                        candidate["volume"] = _volume_label(candidate, weekly, trainable)
                        candidates.append(candidate)
    return candidates


def session_minutes(session: JSON, weekly: JSON) -> float:
    """Warm-up plus the working sets at the bundle's minutes per set."""
    sets = sum(slot["sets"] for slot in session["slots"])
    minutes: float = weekly["warmUpMinutes"] + sets * weekly["minutesPerSet"]
    return minutes


def _build(
    split_id: str,
    layout: tuple[tuple[int, str], ...],
    minutes_by_day: dict[int, int],
    weekly: JSON,
    structures: JSON,
    target: float,
    available_roles: set[str],
) -> JSON | None:
    """One candidate for ``layout``, filled towards ``target``; ``None`` if a session cannot fit."""
    week = _Week(weekly, structures)
    required_by_session: list[list[str]] = []
    for day, session_type in layout:
        definition = structures["sessions"][session_type]
        required = _usable_roles(definition["roles"], available_roles, structures.get("fallbacks", {}))
        optional = [role for role in definition.get("optional", []) if role in available_roles and role not in required]
        capacity = _set_capacity(minutes_by_day[day], weekly)
        if not required or capacity < len(required) * weekly["setsPerExerciseMin"]:
            return None
        week.add_session(day, session_type, capacity, optional)
        required_by_session.append(required)
    for index, required in enumerate(required_by_session):
        for role in required:
            if not week.can_add(index, role, weekly["setsPerExerciseMin"]):
                return None
            week.add_slot(index, role, weekly["setsPerExerciseMin"])
    week.fill(target, accessories=False)
    week.add_accessories(target)
    week.fill(target, accessories=True)

    sessions = [
        {
            "day": session["day"],
            "type": session["type"],
            "slots": session["slots"],
            "minutes": session_minutes(session, weekly),
        }
        for session in week.sessions
    ]
    return {
        "id": _candidate_id(split_id, layout),
        "split": split_id,
        "days": [day for day, _ in layout],
        "sessions": sessions,
        "weeklySets": dict(week.weekly_totals),
        "exposures": _exposures(sessions, structures),
    }


class _Week:
    """A week being filled, with running muscle totals so every cap check is a lookup."""

    def __init__(self, weekly: JSON, structures: JSON) -> None:
        self.weekly = weekly
        self.structures = structures
        majors = set(structures["majorMuscles"])
        self.primaries = {role: _primary_muscles(role, structures) for role in structures["roles"]}
        self.major_primaries = {
            role: [muscle for muscle in muscles if muscle in majors] for role, muscles in self.primaries.items()
        }
        self.sessions: list[JSON] = []
        self.session_totals: list[dict[str, float]] = []
        self.session_set_counts: list[int] = []
        self.weekly_totals: dict[str, float] = {}
        self.day_index: dict[int, int] = {}

    def add_session(self, day: int, session_type: str, capacity: int, optional: list[str]) -> None:
        self.day_index[day] = len(self.sessions)
        self.sessions.append(
            {"day": day, "type": session_type, "capacity": capacity, "slots": [], "optional": optional}
        )
        self.session_totals.append({})
        self.session_set_counts.append(0)

    def neighbour_totals(self, index: int, offset: int) -> dict[str, float]:
        """Muscle totals of the session ``offset`` days away (-1 before, +1 after), if any.

        The week repeats, so Sunday precedes Monday.
        """
        if len(self.sessions) < 2:
            return {}
        neighbour = self.day_index.get((self.sessions[index]["day"] + offset) % DAYS_PER_WEEK)
        return self.session_totals[neighbour] if neighbour is not None else {}

    def can_add(self, index: int, role: str, sets: int) -> bool:
        """Whether ``sets`` more sets of ``role`` in session ``index`` keep time and every muscle cap."""
        if self.session_set_counts[index] + sets > self.sessions[index]["capacity"]:
            return False
        in_session = self.session_totals[index]
        day_before = self.neighbour_totals(index, -1)
        day_after = self.neighbour_totals(index, 1)
        cap = self.weekly["consecutiveDayCap"]
        for muscle, credit in self.structures["roles"][role]["muscles"].items():
            added = sets * credit
            if self.weekly_totals.get(muscle, 0.0) + added > self.weekly["weeklySetsCeiling"]:
                return False
            if in_session.get(muscle, 0.0) + added > self.weekly["sessionSetsCap"]:
                return False
            # This session is the later of a consecutive pair for the muscle.
            if day_before.get(muscle, 0.0) > 0 and in_session.get(muscle, 0.0) + added > cap:
                return False
            # Training the muscle here would make tomorrow's session the later of a pair.
            if in_session.get(muscle, 0.0) == 0 and day_after.get(muscle, 0.0) > cap:
                return False
        return True

    def add_slot(self, index: int, role: str, sets: int) -> None:
        self.sessions[index]["slots"].append({"role": role, "sets": 0})
        self.add_sets(index, len(self.sessions[index]["slots"]) - 1, sets)

    def add_sets(self, index: int, slot_index: int, sets: int) -> None:
        slot = self.sessions[index]["slots"][slot_index]
        slot["sets"] += sets
        self.session_set_counts[index] += sets
        for muscle, credit in self.structures["roles"][slot["role"]]["muscles"].items():
            self.session_totals[index][muscle] = self.session_totals[index].get(muscle, 0.0) + sets * credit
            self.weekly_totals[muscle] = self.weekly_totals.get(muscle, 0.0) + sets * credit

    def fill(self, target: float, accessories: bool) -> None:
        """Add one set at a time where a muscle is furthest below ``target`` and every cap still holds.

        Without ``accessories`` only major muscles are raised; with it, any muscle below target.
        Ties go to the slot with fewer sets, then the earlier day, then the session's role order.
        """
        while True:
            best: tuple[float, int, int, int] | None = None
            best_slot: tuple[int, int] | None = None
            for index, session in enumerate(self.sessions):
                for slot_index, slot in enumerate(session["slots"]):
                    if slot["sets"] + 1 > self.weekly["setsPerExerciseMax"]:
                        continue
                    eligible = self.primaries[slot["role"]] if accessories else self.major_primaries[slot["role"]]
                    deficits = [target - self.weekly_totals.get(muscle, 0.0) for muscle in eligible]
                    if not deficits or max(deficits) <= 0:
                        continue
                    rank = (-max(deficits), slot["sets"], session["day"], slot_index)
                    if best is not None and rank >= best:
                        continue
                    if self.can_add(index, slot["role"], 1):
                        best = rank
                        best_slot = (index, slot_index)
            if best_slot is None:
                return
            self.add_sets(best_slot[0], best_slot[1], 1)

    def add_accessories(self, target: float) -> None:
        """Add optional roles at the minimum sets where time remains and their muscle is below target."""
        minimum = self.weekly["setsPerExerciseMin"]
        for index, session in enumerate(self.sessions):
            for role in session["optional"]:
                below = any(self.weekly_totals.get(muscle, 0.0) < target for muscle in self.primaries[role])
                if below and self.can_add(index, role, minimum):
                    self.add_slot(index, role, minimum)


def _usable_roles(roles: list[str], available_roles: set[str], fallbacks: dict[str, str]) -> list[str]:
    """A session's roles the athlete can do, each missing one replaced by its fallback once.

    ACSM26 treats horizontal and vertical upper-body work as optional per session or per week,
    so a free-weight athlete with no vertical pull gets a second horizontal pull instead of none.
    """
    usable: list[str] = []
    for role in roles:
        choice = role if role in available_roles else fallbacks.get(role)
        if choice is not None and choice in available_roles and choice not in usable:
            usable.append(choice)
    return usable


def _meets_floor(candidate: JSON, weekly: JSON, trainable: set[str]) -> bool:
    """Every trainable major muscle reaches at least the time-limited floor."""
    totals = candidate["weeklySets"]
    return all(totals.get(muscle, 0.0) >= weekly["timeLimitedFloor"] for muscle in trainable)


def _volume_label(candidate: JSON, weekly: JSON, trainable: set[str]) -> str:
    totals = candidate["weeklySets"]
    full = all(totals.get(muscle, 0.0) >= weekly["weeklySetsFloor"] for muscle in trainable)
    return "full" if full else "reduced"


def _trainable_major_muscles(structures: JSON, available_roles: set[str]) -> set[str]:
    """Major muscles that at least one available role trains as a primary muscle."""
    trainable: set[str] = set()
    for role in available_roles:
        if role in structures["roles"]:
            trainable.update(_primary_muscles(role, structures))
    return trainable & set(structures["majorMuscles"])


def _set_capacity(minutes: int, weekly: JSON) -> int:
    """Working sets that fit in ``minutes`` after the warm-up."""
    warm_up: float = weekly["warmUpMinutes"]
    per_set: float = weekly["minutesPerSet"]
    return max(0, math.floor((minutes - warm_up) / per_set))


def _exposures(sessions: list[JSON], structures: JSON) -> dict[str, int]:
    """Sessions per week in which each muscle is a primary target."""
    counts: dict[str, int] = {}
    for session in sessions:
        trained: set[str] = set()
        for slot in session["slots"]:
            trained.update(_primary_muscles(slot["role"], structures))
        for muscle in trained:
            counts[muscle] = counts.get(muscle, 0) + 1
    return counts


def _primary_muscles(role: str, structures: JSON) -> list[str]:
    """Muscles a role trains at full credit."""
    muscles: dict[str, float] = structures["roles"][role]["muscles"]
    return [muscle for muscle, credit in muscles.items() if credit >= 1]


def _candidate_id(split_id: str, layout: tuple[tuple[int, str], ...]) -> str:
    """A stable, readable id such as ``upperLower:Mon-upper,Tue-lower``."""
    parts = [f"{WEEKDAY_SHORT[day]}-{session_type}" for day, session_type in layout]
    return f"{split_id}:{','.join(parts)}"
