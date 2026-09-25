"""Recommendation lifecycle: request → proposed → applied | rejected | expired.

These are ordinary state commands (``requestChange``, ``acceptRecommendation``,
``rejectRecommendation``). A proposal is pinned to the context revision, target
plan id/revision and policy version it was computed against. Acceptance re-runs
the stored request and applies the change only if the decision is identical;
any drift raises ``staleProposal`` and the athlete requests a fresh preview.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..athlete_state import has_active_session, next_plan
from ..errors import DomainError
from ..events import store_plan
from ..rules.adaptation import replan_program
from ..rules.eligibility import decide
from .context import CommandContext
from .plan import WEEKLY_ID_COUNT

JSON = dict[str, Any]

REJECTION_REASONS = ("equipment_unavailable", "prefer_current", "other")


def request_change(context: CommandContext) -> None:
    """Evaluate a request; a ``proposeChange`` outcome is stored as a pending proposal."""
    state, library = context.state, context.library
    request = context.arguments["request"]
    result = decide(state, request, library, context.now)
    context.decision = result
    plan = next_plan(state)
    if result["outcome"] != "proposeChange" or plan is None:
        return
    context.expire_proposals()
    state["recommendations"].append(
        {
            "id": context.next_id(),
            "stateRevision": state["revision"],
            "contextRevision": state["contextRevision"],
            "targetPlanID": plan["id"],
            "targetPlanRevision": plan["revision"],
            "request": request,
            "decision": result,
            "policyVersion": library["policy"]["version"],
            "createdAt": context.now,
            "status": "proposed",
        }
    )
    context.record("recommendation_shown", result["reason"])


def reject(context: CommandContext) -> None:
    """Mark a pending proposal rejected. Rejection is behaviour, not a permanent preference."""
    recommendation = _find(context, context.arguments["id"])
    if recommendation is None or recommendation["status"] != "proposed":
        raise DomainError("staleProposal")
    recommendation.pop("rejectionReason", None)
    reason = context.arguments.get("reason")
    if reason in REJECTION_REASONS:
        recommendation["rejectionReason"] = reason
    recommendation["status"] = "rejected"
    context.record("recommendation_rejected")


def accept(context: CommandContext) -> None:
    """Apply a pending proposal if nothing it depends on has changed. Idempotent once applied."""
    state, library = context.state, context.library
    recommendation = _find(context, context.arguments["id"])
    if recommendation is None:
        raise DomainError("notFound")
    if recommendation["status"] == "applied":
        return
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
    if not still_valid or plan is None:
        raise DomainError("staleProposal")
    reevaluated = decide(state, recommendation["request"], library, context.now)
    if recommendation["request"]["kind"] == "replan":
        _apply_replan(context, recommendation, reevaluated)
        return
    if reevaluated != recommendation["decision"] or reevaluated.get("after") is None:
        raise DomainError("staleProposal")
    applied_plan = deepcopy(reevaluated["after"])
    applied_plan["revision"] = plan["revision"] + 1
    store_plan(applied_plan, state)
    context.record("recommendation_accepted", reevaluated["reason"])
    context.expire_proposals()
    recommendation["status"] = "applied"
    context.record("recommendation_applied", reevaluated["reason"])


def _apply_replan(context: CommandContext, recommendation: JSON, reevaluated: JSON) -> None:
    """ADR-018: replace the program with the proposed week, rebuilt now from the same attendance.

    The decision holds the week, not its ids, so re-evaluating yields an identical decision when
    nothing has changed; the program's ids are taken lazily from this command.
    """
    week = reevaluated.get("week")
    if reevaluated != recommendation["decision"] or week is None:
        raise DomainError("staleProposal")
    state = context.state
    ids = (context.next_id() for _ in range(WEEKLY_ID_COUNT))
    utc_offset = recommendation["request"].get("utcOffset")
    program = replan_program(state, context.library, context.now, ids, week["id"], utc_offset)
    state["previousPrograms"].append(state["program"])
    state["program"] = program
    state.pop("nextPlanOverride", None)
    context.mark_context_changed()
    context.record("recommendation_accepted", reevaluated["reason"])
    context.expire_proposals()
    recommendation["status"] = "applied"
    context.record("recommendation_applied", reevaluated["reason"])


def _find(context: CommandContext, recommendation_id: str) -> JSON | None:
    recommendations: list[JSON] = context.state["recommendations"]
    return next((candidate for candidate in recommendations if candidate["id"] == recommendation_id), None)
