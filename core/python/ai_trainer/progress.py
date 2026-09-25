"""The Progress tab: recorded values per exercise, newest first. Read-only; nothing is estimated.

For each slot of the next plan, the last few comparable sessions are summarised
as the athlete logged them ("20 kg × 8 / 8 / 8 · RIR 2"). The working load is
reported only when it was actually recorded, with how many sessions in a row
it has stayed the same.
"""

from __future__ import annotations

from typing import Any

from .athlete_state import next_plan
from .content import exercises_by_id
from .queries import comparable_sessions, working_logs

JSON = dict[str, Any]

RECENT_SESSIONS = 3


def progress_summary(state: JSON, library: JSON, now: float) -> list[JSON]:
    """One block per exercise in the next plan that has recorded, comparable sessions."""
    plan = next_plan(state)
    if plan is None:
        return []
    exercises = exercises_by_id(library)
    blocks: list[JSON] = []
    for slot in plan["slots"]:
        history = [session for session in comparable_sessions(state, slot, now) if working_logs(session, slot)]
        if not history:
            continue
        exercise = exercises.get(slot["exerciseID"])
        block: JSON = {
            "exerciseID": slot["exerciseID"],
            "name": exercise["name"] if exercise else slot["exerciseID"],
            "unit": slot["equipment"]["unit"],
            "unchangedSessions": _sessions_at_latest_load(history, slot),
            "entries": [_entry(session, slot) for session in history[:RECENT_SESSIONS]],
        }
        latest_load = _single_load(working_logs(history[0], slot))
        if latest_load is not None:
            block["load"] = latest_load
        blocks.append(block)
    return blocks


def _entry(session: JSON, slot: JSON) -> JSON:
    return {"sessionID": session["id"], "date": session["startedAt"], "summary": session_summary(session, slot)}


def session_summary(session: JSON, slot: JSON) -> str:
    """ "20 kg × 8 / 8 / 8 · RIR 2", "load unknown × 8 / 8", "… · ended early"."""
    logs = working_logs(session, slot)
    unit = slot["equipment"]["unit"]
    reps = " / ".join(str(log["reps"]) for log in logs)
    load = _single_load(logs)
    if load is not None:
        text = f"{load:g} {unit} × {reps}"
    elif all(log.get("load") is None for log in logs):
        text = f"load unknown × {reps}"
    else:
        text = " / ".join(f"{_load_text(log)}×{log['reps']}" for log in logs) + f" {unit}"
    rir_values = [log.get("rir") for log in logs]
    known = sorted({value for value in rir_values if value is not None})
    if not known:
        text += " · RIR unknown"
    else:
        text += f" · RIR {known[0]}" if len(known) == 1 else f" · RIR {known[0]}–{known[-1]}"
        if None in rir_values:
            text += " (some unknown)"
    if session["status"] == "endedEarly":
        text += " · ended early"
    return text


def _single_load(logs: list[JSON]) -> float | None:
    """The one load every working set used, if they all recorded the same known load."""
    loads = {log.get("load") for log in logs}
    if len(loads) != 1:
        return None
    (load,) = loads
    return load


def _load_text(log: JSON) -> str:
    load = log.get("load")
    return "?" if load is None else f"{load:g}"


def _sessions_at_latest_load(history: list[JSON], slot: JSON) -> int:
    """How many of the newest sessions in a row used the same recorded load."""
    latest = _single_load(working_logs(history[0], slot))
    if latest is None:
        return 0
    count = 0
    for session in history:
        if _single_load(working_logs(session, slot)) != latest:
            break
        count += 1
    return count
