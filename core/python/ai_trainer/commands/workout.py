"""Commands that run a workout session from check-in to summary."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from ..athlete_state import (
    active_session,
    comparison_key,
    estimated_minutes,
    has_active_session,
    has_working_set,
    next_plan,
    plan_contains_excluded_exercise,
)
from ..errors import DomainError, require
from .context import CommandContext

JSON = dict[str, Any]

MAX_REPS = 1000
MAX_RIR = 10


def validate_set(log: JSON) -> None:
    """Reject impossible set records before they reach state."""
    rir = log.get("rir")
    require(
        0 <= log["reps"] <= MAX_REPS and log["index"] >= 0 and (rir is None or 0 <= rir <= MAX_RIR),
        "invalid",
        "Use nonnegative reps and an optional RIR from 0 to 10.",
    )
    load = log.get("load")
    require(load is None or (math.isfinite(load) and load >= 0), "invalid", "Load must be a nonnegative finite number.")


def start(context: CommandContext) -> None:
    """Begin the next planned session after a check-in.

    A reported concern, an excluded exercise, too little time, or missing
    equipment each stop the start — the athlete previews an adjustment first.
    """
    state = context.state
    require(not has_active_session(state), "invalid", "Resume the existing workout instead of starting a duplicate.")
    program, plan, profile = state.get("program"), next_plan(state), state.get("profile")
    require(program is not None and plan is not None and profile is not None, "notFound")
    assert program is not None and plan is not None and profile is not None
    check_in = context.arguments["checkIn"]
    require(not check_in["painReported"], "invalid", "Pause training guidance and use the reported-concern controls.")
    require(
        not plan_contains_excluded_exercise(state, plan),
        "invalid",
        "This plan contains an excluded activity. No replacement is assumed safe.",
    )
    minutes = check_in.get("minutes")
    require(
        minutes is None or minutes >= estimated_minutes(plan),
        "invalid",
        "Preview a shorter session or reschedule before starting.",
    )
    require(
        not any(slot["equipment"]["kind"] in check_in["unavailableEquipment"] for slot in plan["slots"]),
        "invalid",
        "Review an equipment substitution before starting.",
    )
    session = _new_session(context, program, plan, profile, check_in, status="inProgress")
    session["originalPlan"] = deepcopy(program["plans"][program["sequenceIndex"]])
    state["sessions"].append(session)
    context.expire_proposals()
    context.record("session_started")


def skip(context: CommandContext) -> None:
    """Record the next session as skipped and advance the sequence (TB-02: no doubled work)."""
    state = context.state
    require(not has_active_session(state), "conflict", "Resume the existing workout instead of starting a duplicate.")
    program, plan = state.get("program"), next_plan(state)
    require(program is not None and plan is not None, "conflict")
    assert program is not None and plan is not None
    session = _new_session(context, program, plan, state.get("profile"), context.arguments["checkIn"], status="skipped")
    session["endedAt"] = context.now
    program["sequenceIndex"] = (program["sequenceIndex"] + 1) % len(program["plans"])
    state.pop("nextPlanOverride", None)
    state["sessions"].append(session)
    context.expire_proposals()
    context.record("session_skipped")


def set_paused(context: CommandContext) -> None:
    """Pause or resume. Resuming is refused while an excluded exercise is in the plan."""
    session = context.active_session_or_raise()
    paused = context.arguments["paused"]
    require(
        paused or not plan_contains_excluded_exercise(context.state, session["plan"]),
        "invalid",
        "Reported concern remains active. End this session; resuming does not establish clearance.",
    )
    session["status"] = "paused" if paused else "inProgress"


def save_set(context: CommandContext) -> None:
    """Record one set against a slot of the session's pinned plan and start the rest timer.

    The host sends only what the athlete entered; context key, unit and basis are
    copied from the slot here. A repeated ``operationID`` with identical contents
    is a no-op (AS-03); the same id with different contents is rejected.
    """
    state = context.state
    arguments = context.arguments
    session = context.session_by_id(arguments["sessionID"])
    require(session is not None, "notFound")
    assert session is not None
    slot = next((candidate for candidate in session["plan"]["slots"] if candidate["id"] == arguments["slotID"]), None)
    require(slot is not None, "notFound")
    assert slot is not None
    log = _set_log(arguments, slot, context.now)
    validate_set(log)
    if log["operationID"] in state["operations"]:
        existing = next((item for item in session["logs"] if item["operationID"] == log["operationID"]), None)
        require(existing == log, "invalid", "Operation ID was reused with different contents.")
        return
    require(session["status"] == "inProgress")
    if log["kind"] == "working":
        require(
            log["index"] < slot["workingSets"] and not has_working_set(session, slot["id"], log["index"]),
            "invalid",
            "This working set is already logged. Correct it in History instead.",
        )
    session["logs"].append(log)
    session["restEndsAt"] = log["occurredAt"] + slot["restSeconds"]
    state["operations"].append(log["operationID"])
    context.expire_proposals()
    context.record("set_saved", occurred_at=log["occurredAt"])


def finish(context: CommandContext) -> None:
    """Close the active session. Unlogged working sets are recorded as omissions, not zeros."""
    state = context.state
    session = context.active_session_or_raise()
    reason = context.arguments["reason"]
    for slot in session["plan"]["slots"]:
        for index in range(slot["workingSets"]):
            if not has_working_set(session, slot["id"], index):
                session["omissions"][f"{slot['id']}:{index}"] = reason
    session["status"] = "endedEarly" if session["omissions"] else "completed"
    session["endedAt"] = context.now
    session.pop("restEndsAt", None)
    program = state.get("program")
    if program and program["plans"]:
        program["sequenceIndex"] = (program["sequenceIndex"] + 1) % len(program["plans"])
    state.pop("nextPlanOverride", None)
    context.expire_proposals()
    context.record("session_ended", session["status"])


def report_pain(context: CommandContext) -> None:
    """TB-08: a reported concern excludes the exercise and pauses any active session."""
    state = context.state
    exercise_id = context.arguments["exerciseID"]
    if exercise_id not in state["painExclusions"]:
        state["painExclusions"].append(exercise_id)
    context.mark_context_changed()
    session = active_session(state)
    if session is not None:
        session["status"] = "paused"
    context.record("guidance_withheld", "REPORTED_PAIN")


def exclude(context: CommandContext) -> None:
    """Toggle an explicit user exclusion; excluding an exercise in the active plan pauses it."""
    state = context.state
    require(state.get("profile") is not None, "notFound")
    exclusions = state["profile"]["excludedExercises"]
    exercise_id = context.arguments["exerciseID"]
    if context.arguments["excluded"]:
        if exercise_id not in exclusions:
            exclusions.append(exercise_id)
        session = active_session(state)
        if session is not None and any(slot["exerciseID"] == exercise_id for slot in session["plan"]["slots"]):
            session["status"] = "paused"
    elif exercise_id in exclusions:
        exclusions.remove(exercise_id)
    context.mark_context_changed()


def _set_log(arguments: JSON, slot: JSON, occurred_at: float) -> JSON:
    """A SetLog record at ``occurred_at``. Absent load or RIR stays absent — unknown is never defaulted."""
    log: JSON = {
        "id": arguments["logID"],
        "operationID": arguments["operationID"],
        "revision": 1,
        "prescriptionID": slot["id"],
        "contextKey": comparison_key(slot),
        "index": arguments["index"],
        "kind": arguments["kind"],
        "unit": slot["equipment"]["unit"],
        "basis": slot["equipment"]["basis"],
        "reps": arguments["reps"],
        "occurredAt": occurred_at,
        "conflicted": False,
    }
    for optional in ("load", "rir"):
        if arguments.get(optional) is not None:
            log[optional] = arguments[optional]
    return log


def _new_session(
    context: CommandContext,
    program: JSON,
    plan: JSON,
    profile: JSON | None,
    check_in: JSON,
    status: str,
) -> JSON:
    if status not in ("inProgress", "skipped"):
        raise DomainError("unsupported")
    return {
        "id": context.next_id(),
        "programID": program["id"],
        "programRevision": program["revision"],
        "originalPlan": deepcopy(plan),
        "plan": deepcopy(plan),
        "status": status,
        "startedAt": context.now,
        "timeZone": (profile or {}).get("timeZone", "UTC"),
        "checkIn": check_in,
        "logs": [],
        "omissions": {},
    }
