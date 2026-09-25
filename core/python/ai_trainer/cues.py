"""Spoken coaching cues for the workout in progress (ADR-022).

Borrowed from Apple's Workout Buddy, without a language model. Every word is built here from the
plan and the athlete's own logged sets, so nothing spoken can be invented: reps and load come
from the prescription, "last time" from recorded comparable sessions, and an unknown load is
said to be unknown. The host only reads the text aloud (AVSpeechSynthesizer).

Three cues, each ``None`` when it does not apply:

- ``afterSet``: once a set is logged — what was done, the rest, and what comes next;
- ``restOver``: when the rest timer ends — the next set;
- ``next``: the next set on its own, for when the athlete asks.
"""

from __future__ import annotations

from typing import Any

from .athlete_state import active_session, has_working_set
from .content import exercises_by_id
from .queries import comparable_sessions, working_logs

JSON = dict[str, Any]

UNIT_WORDS = {"kg": "kilograms", "lb": "pounds"}
MINUTE = 60


def workout_cues(state: JSON, library: JSON, now: float) -> JSON | None:
    """``{afterSet?, restOver?, next?}`` for the active session, or ``None`` without one."""
    session = active_session(state)
    if session is None:
        return None
    names = {exercise_id: exercise["name"] for exercise_id, exercise in exercises_by_id(library).items()}
    upcoming = _next_set(session)
    last_log = _last_working_log(session)
    cues: JSON = {}
    if upcoming is not None:
        slot, index = upcoming
        new_exercise = last_log is None or last_log["prescriptionID"] != slot["id"]
        cues["next"] = _next_sentence(state, slot, index, names, now, with_history=new_exercise)
        cues["restOver"] = "Rest's over. " + _set_sentence(slot, index, names)
    if last_log is not None:
        done_slot = next(s for s in session["plan"]["slots"] if s["id"] == last_log["prescriptionID"])
        done = f"Set {last_log['index'] + 1} of {_name(done_slot, names)} done."
        rest = f"Rest {_duration(done_slot['restSeconds'])}."
        follow = cues.get("next") or "That was the last planned set. Tap Finish when you're done."
        cues["afterSet"] = f"{done} {rest} {follow}"
    return cues


def _next_set(session: JSON) -> tuple[JSON, int] | None:
    """The first planned working set, in plan order, with no log yet."""
    for slot in session["plan"]["slots"]:
        for index in range(slot["workingSets"]):
            if not has_working_set(session, slot["id"], index):
                return slot, index
    return None


def _last_working_log(session: JSON) -> JSON | None:
    """The most recently logged working set: logs are appended in the order they were saved."""
    working = [log for log in session["logs"] if log["kind"] == "working"]
    return working[-1] if working else None


def _next_sentence(state: JSON, slot: JSON, index: int, names: dict[str, str], now: float, with_history: bool) -> str:
    sentence = "Next: " + _set_sentence(slot, index, names)
    if with_history:
        history = _last_time(state, slot, now)
        if history:
            sentence += " " + history
    return sentence


def _set_sentence(slot: JSON, index: int, names: dict[str, str]) -> str:
    reps = slot["targets"][index] if index < len(slot["targets"]) else slot["lowerReps"]
    return f"{_name(slot, names)}, set {index + 1} of {slot['workingSets']}: {reps} reps at {_load(slot)}."


def _last_time(state: JSON, slot: JSON, now: float) -> str | None:
    """ "Last time you did 8, 8 and 7 reps at 100 kilograms." from the latest comparable session."""
    for session in comparable_sessions(state, slot, now):
        logs = working_logs(session, slot)
        if not logs:
            continue
        reps = _join([str(log["reps"]) for log in logs])
        loads = {log.get("load") for log in logs}
        if len(loads) == 1 and None not in loads:
            load = next(iter(loads))
            return f"Last time you did {reps} reps at {load:g} {_unit(slot)}."
        return f"Last time you did {reps} reps."
    return None


def _name(slot: JSON, names: dict[str, str]) -> str:
    exercise_id: str = slot["exerciseID"]
    return names.get(exercise_id, exercise_id)


def _load(slot: JSON) -> str:
    load = slot.get("load")
    return "a load you choose" if load is None else f"{load:g} {_unit(slot)}"


def _unit(slot: JSON) -> str:
    unit: str = slot["equipment"]["unit"]
    return UNIT_WORDS.get(unit, unit)


def _duration(seconds: int) -> str:
    """ "90 seconds", "2 minutes", "2 minutes 30 seconds"."""
    minutes, rest = divmod(seconds, MINUTE)
    if minutes < 2 and seconds < 2 * MINUTE:
        return f"{seconds} seconds"
    text = f"{minutes} minute{'s' if minutes != 1 else ''}"
    return text + (f" {rest} seconds" if rest else "")


def _join(items: list[str]) -> str:
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]
