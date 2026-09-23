"""Recommendation lifecycle: request → proposed → applied | rejected | expired.

A proposal is pinned to the context revision, target plan id/revision and
policy version it was computed against. Acceptance re-runs the stored request
and applies the change only if the decision is byte-for-byte identical; any
drift raises ``staleProposal`` and the athlete requests a fresh preview.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .athlete_state import has_active_session, next_plan
from .errors import DomainError
from .events import expire_proposals, record_event, store_plan
from .rules.eligibility import decide

JSON = dict[str, Any]

REJECTION_REASONS = ("equipment_unavailable", "prefer_current", "other")

# Persisted recommendations keep the original Swift Codable enum shape
# (``{"progression": {"_0": slotID}}``); operations use explicit named fields.
_REQUEST_FIELDS: dict[str, list[str]] = {
    "progression": ["slotID"],
    "shorten": ["minutes"],
    "substitute": ["slotID", "alternativeID"],
    "reschedule": ["date"],
}


def to_stored_request(request: JSON) -> JSON:
    kind = request["kind"]
    fields = _REQUEST_FIELDS[kind]
    return {kind: {f"_{position}": request[field] for position, field in enumerate(fields)}}


def to_explicit_request(stored: JSON) -> JSON:
    kind, values = next(iter(stored.items()))
    fields = _REQUEST_FIELDS[kind]
    return {"kind": kind, **{field: values[f"_{position}"] for position, field in enumerate(fields)}}


def handle_recommendation(payload: JSON) -> JSON:
    """Dispatch ``request`` / ``accept`` / ``reject`` on a copy of the payload's state."""
    state = deepcopy(payload["state"])
    library, now, ids = payload["library"], payload["now"], payload["ids"]
    operation = payload["operation"]
    if operation == "request":
        return _request(state, payload["request"], library, now, ids)
    if operation == "reject":
        return _reject(state, payload["id"], payload.get("reason"), now, ids)
    if operation == "accept":
        return _accept(state, payload["id"], library, now, ids)
    raise DomainError("unsupported")


def _request(state: JSON, request: JSON, library: JSON, now: float, ids: list[str]) -> JSON:
    result = decide(state, request, library, now)
    plan = next_plan(state)
    if result["outcome"] == "proposeChange" and plan:
        expire_proposals(state)
        state["recommendations"].append(
            {
                "id": ids[0],
                "stateRevision": state["revision"],
                "contextRevision": state["contextRevision"],
                "targetPlanID": plan["id"],
                "targetPlanRevision": plan["revision"],
                "request": to_stored_request(request),
                "decision": result,
                "policyVersion": library["policy"]["version"],
                "createdAt": now,
                "status": "proposed",
            }
        )
        record_event(state, "recommendation_shown", now, ids[1], result["reason"])
    return {"state": state, "decision": result}


def _reject(state: JSON, recommendation_id: str, reason: str | None, now: float, ids: list[str]) -> JSON:
    recommendation = _find(state, recommendation_id)
    if recommendation is None or recommendation["status"] != "proposed":
        raise DomainError("staleProposal")
    recommendation.pop("rejectionReason", None)
    if reason in REJECTION_REASONS:
        recommendation["rejectionReason"] = reason
    recommendation["status"] = "rejected"
    # Rejection is behaviour, not a permanent preference or proof of an outcome.
    record_event(state, "recommendation_rejected", now, ids[0])
    return {"state": state}


def _accept(state: JSON, recommendation_id: str, library: JSON, now: float, ids: list[str]) -> JSON:
    recommendation = _find(state, recommendation_id)
    if recommendation is None:
        raise DomainError("notFound")
    if recommendation["status"] == "applied":
        return {"state": state}  # idempotent
    plan = next_plan(state)
    still_valid = (
        recommendation["status"] == "proposed"
        and recommendation["contextRevision"] == state["contextRevision"]
        and recommendation["policyVersion"] == library["policy"]["version"]
        and plan is not None
        and recommendation["targetPlanID"] == plan["id"]
        and recommendation["targetPlanRevision"] == plan["revision"]
        and not has_active_session(state)
    )
    if not still_valid:
        raise DomainError("staleProposal")
    assert plan is not None
    reevaluated = decide(state, to_explicit_request(recommendation["request"]), library, now)
    if reevaluated != recommendation["decision"] or reevaluated.get("after") is None:
        raise DomainError("staleProposal")
    applied_plan = deepcopy(reevaluated["after"])
    applied_plan["revision"] = plan["revision"] + 1
    store_plan(applied_plan, state)
    record_event(state, "recommendation_accepted", now, ids[0], reevaluated["reason"])
    expire_proposals(state)
    recommendation["status"] = "applied"
    record_event(state, "recommendation_applied", now, ids[1], reevaluated["reason"])
    return {"state": state}


def _find(state: JSON, recommendation_id: str) -> JSON | None:
    return next((candidate for candidate in state["recommendations"] if candidate["id"] == recommendation_id), None)
