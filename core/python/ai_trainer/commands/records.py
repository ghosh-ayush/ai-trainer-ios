"""Commands that correct, reconcile or delete recorded performance."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..athlete_state import is_active
from ..errors import require
from .context import CommandContext
from .workout import validate_set

JSON = dict[str, Any]


def correct_set(context: CommandContext) -> bool:
    """Apply a correction if the caller saw the current revision; otherwise keep both versions.

    Returns ``True`` when applied, ``False`` when a Conflict record was created
    instead (AS-04/AS-06: no silent winner).
    """
    state = context.state
    arguments = context.arguments
    session, current = _session_and_log(context, arguments["sessionID"], arguments["logID"])
    incoming = deepcopy(current)
    incoming.pop("load", None)
    incoming.pop("rir", None)
    for key in ("load", "rir"):
        if arguments.get(key) is not None:
            incoming[key] = arguments[key]
    incoming.update(reps=arguments["reps"], revision=current["revision"] + 1, conflicted=False)
    validate_set(incoming)
    context.expire_proposals()

    stale = current["revision"] != arguments["expectedRevision"] or current["conflicted"]
    if stale:
        state["conflicts"].append(
            {"id": context.next_id(), "sessionID": session["id"], "current": deepcopy(current), "incoming": incoming}
        )
        current["conflicted"] = True
        context.record("sync_conflict")
        return False

    state["audits"].append({"id": context.next_id(), "previous": deepcopy(current), "correctedAt": context.now})
    session["logs"][session["logs"].index(current)] = incoming
    context.record("set_corrected")
    return True


def resolve_conflict(context: CommandContext) -> None:
    """The athlete picks which version survives; the loser is kept in the audit trail."""
    state = context.state
    conflict = next((candidate for candidate in state["conflicts"] if candidate["id"] == context.arguments["id"]), None)
    require(conflict is not None, "notFound")
    assert conflict is not None
    session, current = _session_and_log(context, conflict["sessionID"], conflict["current"]["id"])
    chosen = deepcopy(conflict["incoming"] if context.arguments["useIncoming"] else current)
    chosen.update(revision=current["revision"] + 1, conflicted=False)
    validate_set(chosen)
    state["audits"].append({"id": context.next_id(), "previous": current, "correctedAt": context.now})
    session["logs"][session["logs"].index(current)] = chosen
    state["conflicts"] = [candidate for candidate in state["conflicts"] if candidate["current"]["id"] != current["id"]]
    context.expire_proposals()
    context.record("conflict_resolved")


def delete_session(context: CommandContext) -> None:
    """AS-08: delete a completed session and every record that depends on its logs."""
    state = context.state
    session = context.session_by_id(context.arguments["id"])
    require(session is not None and not is_active(session))
    assert session is not None
    log_ids = {log["id"] for log in session["logs"]}
    operation_ids = {log["operationID"] for log in session["logs"]}
    state["sessions"].remove(session)
    state["audits"] = [audit for audit in state["audits"] if audit["previous"]["id"] not in log_ids]
    state["conflicts"] = [conflict for conflict in state["conflicts"] if conflict["sessionID"] != session["id"]]
    state["recommendations"] = [
        recommendation
        for recommendation in state["recommendations"]
        if not any(evidence["id"] in log_ids for evidence in recommendation["decision"]["evidence"])
    ]
    state["operations"] = [operation for operation in state["operations"] if operation not in operation_ids]
    context.expire_proposals()


def _session_and_log(context: CommandContext, session_id: str, log_id: str) -> tuple[JSON, JSON]:
    session = context.session_by_id(session_id)
    require(session is not None, "notFound")
    assert session is not None
    log = next((candidate for candidate in session["logs"] if candidate["id"] == log_id), None)
    require(log is not None, "notFound")
    assert log is not None
    return session, log
