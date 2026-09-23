"""Read-only queries over history. Deterministic ordering, no mutation."""

from __future__ import annotations

from typing import Any

from .athlete_state import comparison_key, is_active

JSON = dict[str, Any]


def comparable_sessions(state: JSON, slot: JSON, now: float) -> list[JSON]:
    """Completed (or ended-early) sessions that contain a slot comparable to ``slot``.

    Ordered newest first; ties broken by session id so replay is deterministic.
    Active, skipped and future-dated sessions are excluded.
    """
    key = comparison_key(slot)
    matching = [
        session
        for session in state["sessions"]
        if not is_active(session)
        and session["status"] != "skipped"
        and session["startedAt"] <= now
        and any(comparison_key(candidate) == key for candidate in session["plan"]["slots"])
    ]
    return sorted(matching, key=lambda session: (-session["startedAt"], session["id"]))


def working_logs(session: JSON, slot: JSON) -> list[JSON]:
    """Working sets logged against the slot's comparison key, in set order."""
    key = comparison_key(slot)
    logs = [log for log in session["logs"] if log["contextKey"] == key and log["kind"] == "working"]
    return sorted(logs, key=lambda log: log["index"])


def evidence_from(logs: list[JSON]) -> list[JSON]:
    """The id/revision pairs a decision relied on."""
    return [{"id": log["id"], "revision": log["revision"]} for log in logs]
