"""What the Today screen shows about each slot, as a read-only query.

For every slot of the next plan the core evaluates the progression request
(the same ``decide`` call a proposal would use) and turns the answer into a
short card: a needs-state ("Set your load to unlock progression"), a pending
proposal, or a paused/excluded state. It also names at most one slot whose
progression the host should request automatically, so proposals appear
without a separate "Review progression" step. Nothing here mutates state.
"""

from __future__ import annotations

from typing import Any

from .athlete_state import next_plan
from .content import exercises_by_id
from .queries import comparable_sessions
from .rules.adaptation import replan_due
from .rules.eligibility import decide
from .rules.progression import qualifying_streak

JSON = dict[str, Any]

# reason -> (tone, title, body, action). Tones: default, accent, warn, danger.
# Actions name the control the card offers: setLoad opens the load sheet, swap the curated swap.
STATUS_COPY: dict[str, tuple[str, str, str, str | None]] = {
    "BASELINE_REQUIRED": (
        "warn",
        "Set your load to unlock progression",
        "The app never estimates your strength. Tap the load chip.",
        "setLoad",
    ),
    "EQUIPMENT_STEP_UNKNOWN": (
        "warn",
        "Add your equipment steps",
        "Progression needs the next load you actually have. No increment is invented.",
        "setLoad",
    ),
    "HISTORY_STALE": (
        "warn",
        "Reconfirm your working load",
        "Your last comparable session is too old to use. Confirm the load you use now.",
        "setLoad",
    ),
    "LOAD_CONTEXT_CHANGED": (
        "warn",
        "Recorded load differs from the plan",
        "Confirm the working load you want to keep. Evidence is not transferred between loads.",
        "setLoad",
    ),
    "REPORTED_PAIN": (
        "danger",
        "Guidance paused — you reported pain",
        "Swap this exercise to unblock progression. A different exercise is not assumed safe.",
        "swap",
    ),
    "EXERCISE_EXCLUDED": (
        "danger",
        "Excluded from guidance",
        "You excluded this exercise in You. Swap it for today or re-enable it there.",
        "swap",
    ),
    "EVIDENCE_CONFLICT": (
        "warn",
        "Resolve a conflicting set",
        "Two versions of one set exist. Pick one in Progress before progression continues.",
        None,
    ),
    "EFFORT_UNKNOWN": (
        "default",
        "Effort unknown",
        "Add reps in reserve when you log sets. Unknown effort never counts as easy.",
        None,
    ),
    "INCOMPLETE_EXPOSURE": (
        "default",
        "Last session was incomplete",
        "Log every working set in one session for it to count. This is not a strength-failure diagnosis.",
        None,
    ),
    "TARGET_NOT_QUALIFIED": (
        "default",
        "Repeat these targets",
        "The rep or effort criterion was not met last time. Keep the current load.",
        None,
    ),
    "MODIFIED_EXPOSURE": (
        "default",
        "Adjusted session does not count",
        "A shortened or swapped session is not an original exposure. Train the full plan next time.",
        None,
    ),
    "SESSION_OVERRIDE_ACTIVE": (
        "default",
        "Temporary change in place",
        "Progression resumes after today's adjusted session.",
        None,
    ),
    "INCREMENT_EXCEEDS_BOUND": (
        "default",
        "Next load step is too large",
        "Your next available load exceeds the policy's permitted change. Keep the load or add a smaller step.",
        "setLoad",
    ),
    "LOADING_POLICY_UNAVAILABLE": (
        "default",
        "Load changes are manual here",
        "Machine settings and assistance need equipment-specific reviewed progression.",
        None,
    ),
    "UNREVIEWED_EXERCISE": (
        "default",
        "No guidance policy",
        "This exercise has no enabled guidance policy.",
        None,
    ),
}

KEPT_CURRENT = (
    "default",
    "Keeping the current plan",
    "You kept this plan. A new proposal can follow your next session.",
)


def today_status(state: JSON, library: JSON, now: float) -> JSON:
    """Per-slot cards for the next plan, pending proposal titles, and at most one slot to auto-request."""
    plan = next_plan(state)
    if plan is None:
        return {"slots": [], "proposals": [], "autoRequest": None}
    exercises = exercises_by_id(library)
    pending = [rec for rec in state["recommendations"] if rec["status"] == "proposed"]
    slots: list[JSON] = []
    auto_request: str | None = None
    for slot in plan["slots"]:
        request = {"kind": "progression", "slotID": slot["id"]}
        decision = decide(state, request, library, now)
        if any(rec["request"].get("slotID") == slot["id"] for rec in pending):
            continue  # the proposal card stands in for the status card
        if decision["outcome"] == "proposeChange":
            if _already_answered(state, plan, request):
                slots.append(_card(slot, decision, *KEPT_CURRENT, None))
            elif auto_request is None and not pending:
                auto_request = slot["id"]
            continue
        status = _status_for(state, slot, decision, library, now)
        if status is not None:
            slots.append(status)
    proposals = [_proposal(rec, plan, exercises) for rec in pending]
    today: JSON = {"slots": slots, "proposals": proposals, "autoRequest": auto_request}
    if auto_request is None and not pending and _replan_to_offer(state, plan, library, now):
        today["autoReplan"] = True
    return today


def _replan_to_offer(state: JSON, plan: JSON, library: JSON, now: float) -> bool:
    """ADR-018: a replan is due, would propose a different week, and was not already rejected."""
    request = {"kind": "replan"}
    if not replan_due(state, library, now) or _already_answered(state, plan, request):
        return False
    outcome: str = decide(state, request, library, now)["outcome"]
    return outcome == "proposeChange"


def _status_for(state: JSON, slot: JSON, decision: JSON, library: JSON, now: float) -> JSON | None:
    reason = decision["reason"]
    if reason in ("SESSION_ACTIVE", "PROFILE_REQUIRED", "POLICY_NOT_APPROVED", "REPEAT_TARGET"):
        return None  # shown once for the whole screen, or nothing to say
    if reason in ("NO_COMPARABLE_HISTORY", "MORE_EXPOSURES_REQUIRED"):
        return _exposure_progress(state, slot, decision, library, now)
    tone, title, body, action = STATUS_COPY.get(
        reason, ("default", "No change proposed", decision["explanation"], None)
    )
    return _card(slot, decision, tone, title, body, action)


def _exposure_progress(state: JSON, slot: JSON, decision: JSON, library: JSON, now: float) -> JSON:
    """ "1 of 2 comparable sessions done" — counted with the same streak rule progression uses."""
    policy = library["policy"]
    required = policy["requiredExposures"]
    history = comparable_sessions(state, slot, now)
    done = 0
    if history and slot.get("load") is not None:
        done, _ = qualifying_streak(history, slot, policy, slot["load"], now)
    remaining = max(required - done, 1)
    sessions = "one more full session" if remaining == 1 else f"{remaining} more full sessions"
    title = f"{done} of {required} comparable sessions done"
    body = f"Log {sessions} at this load and a change can be reviewed."
    return _card(slot, decision, "default", title, body, None)


def _card(slot: JSON, decision: JSON, tone: str, title: str, body: str, action: str | None) -> JSON:
    card: JSON = {
        "slotID": slot["id"],
        "reason": decision["reason"],
        "tone": tone,
        "title": title,
        "body": body,
    }
    if action is not None:
        card["action"] = action
    return card


def _already_answered(state: JSON, plan: JSON, request: JSON) -> bool:
    """A rejected proposal for the same request against the same context is not re-proposed."""
    return any(
        rec["request"] == request
        and rec["status"] == "rejected"
        and rec["contextRevision"] == state["contextRevision"]
        and rec["targetPlanID"] == plan["id"]
        and rec["targetPlanRevision"] == plan["revision"]
        for rec in state["recommendations"]
    )


def _proposal(recommendation: JSON, plan: JSON, exercises: dict[str, JSON]) -> JSON:
    """Title and body for one pending proposal card."""
    request = recommendation["request"]
    decision = recommendation["decision"]
    after = decision.get("after") or plan
    title = "Proposed change"
    slot_id = request.get("slotID")
    before_slot = _slot(plan, slot_id)
    after_slot = _slot(after, slot_id)
    if request["kind"] == "progression" and before_slot and after_slot:
        unit = before_slot["equipment"]["unit"]
        if after_slot.get("load") != before_slot.get("load"):
            title = f"Proposed · {_number(before_slot.get('load'))} → {_number(after_slot.get('load'))} {unit}"
        else:
            title = f"Proposed · {_targets(before_slot)} → {_targets(after_slot)} reps"
    elif request["kind"] == "substitute" and after_slot:
        name = exercises.get(after_slot["exerciseID"], {}).get("name", after_slot["exerciseID"])
        title = f"Proposed · swap to {name}"
    elif request["kind"] == "shorten":
        title = f"Proposed · {len(after['slots'])} exercises · ~{_minutes(after)} min"
    elif request["kind"] == "reschedule":
        title = "Proposed · move this session"
    elif request["kind"] == "replan" and decision.get("week"):
        week = decision["week"]
        days = week["sessionsPerWeek"]
        title = f"Proposed · {week['name']} · {days} day{'s' if days != 1 else ''} a week"
    proposal: JSON = {
        "recommendationID": recommendation["id"],
        "kind": request["kind"],
        "title": title,
        "body": decision["explanation"],
    }
    if slot_id is not None:
        proposal["slotID"] = slot_id
    return proposal


def _slot(plan: JSON, slot_id: str | None) -> JSON | None:
    return next((slot for slot in plan["slots"] if slot["id"] == slot_id), None)


def _targets(slot: JSON) -> str:
    return " / ".join(str(target) for target in slot["targets"])


def _minutes(plan: JSON) -> int:
    total: int = plan["warmUpMinutes"] + sum(slot["estimatedMinutes"] for slot in plan["slots"])
    return total


def _number(value: float | None) -> str:
    """20.0 → "20", 22.5 → "22.5"; unknown stays written out."""
    if value is None:
        return "unknown"
    return f"{value:g}"
