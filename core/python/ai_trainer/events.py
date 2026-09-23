"""Local analytics events and proposal expiry — the two side effects every
mutation shares."""

from __future__ import annotations

from typing import Any

JSON = dict[str, Any]


def record_event(state: JSON, name: str, now: float, event_id: str, reason: str | None = None) -> None:
    """Append a controlled-vocabulary analytics event to local state.

    ``stateRevision`` is the revision the host will assign when it commits
    this candidate state (current + 1).
    """
    event: JSON = {
        "id": event_id,
        "name": name,
        "occurredAt": now,
        "stateRevision": state["revision"] + 1,
    }
    if reason is not None:
        event["reason"] = reason
    state["events"].append(event)


def expire_proposals(state: JSON) -> None:
    """Any pending proposal becomes stale once state changes underneath it."""
    for recommendation in state["recommendations"]:
        if recommendation["status"] == "proposed":
            recommendation["status"] = "expired"


def store_plan(plan: JSON, state: JSON) -> None:
    """Write ``plan`` back to wherever the next plan lives.

    Temporary (modified) plans go to ``nextPlanOverride``; otherwise the
    program's sequenced slot is replaced in place.
    """
    if plan["modified"] or state.get("nextPlanOverride") is not None:
        state["nextPlanOverride"] = plan
    else:
        program = state["program"]
        program["plans"][program["sequenceIndex"]] = plan
