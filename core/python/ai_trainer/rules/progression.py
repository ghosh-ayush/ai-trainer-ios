"""TB-04: load and rep progression on comparable, confirmed evidence.

The rule is a conservative double progression:

1. Work up the rep range first — one extra total target rep per proposal.
2. Only when every working set reaches the top of the range, at or above the
   required reps-in-reserve, in ``requiredExposures`` consecutive comparable
   sessions, propose the next *available* equipment step — never an invented
   increment, and never more than ``maximumIncreaseFraction``.

Every early return names the reason so the athlete sees *why* nothing changed.
Nothing here is an approved real-world prescription; parameters come from the
policy record supplied by the host.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..messages import Decision, decision
from ..queries import comparable_sessions, evidence_from, working_logs

JSON = dict[str, Any]

SECONDS_PER_DAY = 86400
LOAD_EPSILON = 0.000001
FRACTION_EPSILON = 0.0000001
EXTERNAL_LOAD_BASES = ("total", "perHand")


def propose_progression(state: JSON, plan: JSON, slot: JSON, policy: JSON, now: float) -> Decision:
    """Decide whether ``slot`` in ``plan`` should progress, and how."""
    if plan["modified"]:
        return decision("SESSION_OVERRIDE_ACTIVE")
    if slot["equipment"]["basis"] not in EXTERNAL_LOAD_BASES:
        return decision("LOADING_POLICY_UNAVAILABLE")

    baseline_load = slot.get("load")
    if baseline_load is None or baseline_load <= 0:
        return decision("BASELINE_REQUIRED")

    history = comparable_sessions(state, slot, now)
    if not history:
        return decision("NO_COMPARABLE_HISTORY")

    latest = history[0]
    if _days_between(latest["startedAt"], now) > policy["historyDays"]:
        return decision("HISTORY_STALE")

    latest_logs = working_logs(latest, slot)
    if latest["plan"]["modified"]:
        return decision("MODIFIED_EXPOSURE")
    if any(log["conflicted"] for log in latest_logs):
        return decision("EVIDENCE_CONFLICT")
    if not _all_working_sets_present(latest_logs, slot):
        return decision("INCOMPLETE_EXPOSURE")
    if not all(log.get("load") == baseline_load for log in latest_logs):
        return decision("LOAD_CONTEXT_CHANGED")
    if any(log.get("rir") is None for log in latest_logs):
        return decision("EFFORT_UNKNOWN")
    if not all(_meets_minimum(log, slot, policy) for log in latest_logs):
        return decision("TARGET_NOT_QUALIFIED")

    proposed_plan = deepcopy(plan)
    proposed_slot = next((candidate for candidate in proposed_plan["slots"] if candidate["id"] == slot["id"]), None)
    if proposed_slot is None:
        return decision("SLOT_MISSING")

    if not all(log["reps"] >= slot["upperReps"] for log in latest_logs):
        return _propose_one_more_rep(latest_logs, slot, proposed_slot, proposed_plan)

    qualifying_logs = _consecutive_qualifying_logs(history, slot, policy, baseline_load, now)
    if qualifying_logs is None:
        return decision("MORE_EXPOSURES_REQUIRED")

    next_step = _next_available_load(slot, baseline_load)
    if next_step is None:
        return decision("EQUIPMENT_STEP_UNKNOWN")
    if (next_step - baseline_load) / baseline_load > policy["maximumIncreaseFraction"] + FRACTION_EPSILON:
        return decision("INCREMENT_EXCEEDS_BOUND")

    proposed_slot["load"] = next_step
    proposed_slot["targets"] = [slot["lowerReps"]] * slot["workingSets"]
    return decision("QUALIFYING_EXPOSURES_COMPLETE", proposed_plan, evidence_from(qualifying_logs))


# --- helpers -----------------------------------------------------------------


def _days_between(earlier: float, later: float) -> float:
    return (later - earlier) / SECONDS_PER_DAY


def _all_working_sets_present(logs: list[JSON], slot: JSON) -> bool:
    expected_indexes = set(range(slot["workingSets"]))
    return len(logs) == slot["workingSets"] and {log["index"] for log in logs} == expected_indexes


def _meets_minimum(log: JSON, slot: JSON, policy: JSON) -> bool:
    return bool(log["rir"] >= policy["minimumRIR"] and log["reps"] >= slot["lowerReps"])


def _propose_one_more_rep(latest_logs: list[JSON], slot: JSON, proposed_slot: JSON, proposed_plan: JSON) -> Decision:
    """Rep progression: allocate exactly one extra target rep to the first set below the top."""
    targets = [min(log["reps"], slot["upperReps"]) for log in latest_logs]
    for index, reps in enumerate(targets):
        if reps < slot["upperReps"]:
            targets[index] += 1
            break
    if targets == slot["targets"]:
        return decision("REPEAT_TARGET")
    proposed_slot["targets"] = targets
    return decision("NEXT_TARGET_REP", proposed_plan, evidence_from(latest_logs))


def qualifying_streak(
    history: list[JSON], slot: JSON, policy: JSON, baseline_load: float, now: float
) -> tuple[int, list[JSON]]:
    """How many of the most recent comparable sessions qualify in a row, and their working logs.

    Counting stops at ``requiredExposures``. A session breaks the streak if it
    was modified, is outside the history window, follows a gap longer than
    ``maximumGapDays``, is incomplete, or any set is conflicted, at a different
    load, below the top of the range, or below the required RIR.
    """
    qualifying: list[JSON] = []
    previous_start = now
    count = 0
    for session in history:
        logs = working_logs(session, slot)
        session_qualifies = (
            not session["plan"]["modified"]
            and _days_between(session["startedAt"], now) <= policy["historyDays"]
            and _days_between(session["startedAt"], previous_start) <= policy["maximumGapDays"]
            and _all_working_sets_present(logs, slot)
            and all(
                not log["conflicted"]
                and log.get("load") == baseline_load
                and log["reps"] >= slot["upperReps"]
                and log.get("rir") is not None
                and log["rir"] >= policy["minimumRIR"]
                for log in logs
            )
        )
        if not session_qualifies:
            break
        count += 1
        qualifying.extend(logs)
        previous_start = session["startedAt"]
        if count >= policy["requiredExposures"]:
            break
    return count, qualifying


def _consecutive_qualifying_logs(
    history: list[JSON], slot: JSON, policy: JSON, baseline_load: float, now: float
) -> list[JSON] | None:
    """Working logs of the qualifying streak, or ``None`` when it is shorter than required."""
    count, logs = qualifying_streak(history, slot, policy, baseline_load, now)
    return logs if count >= policy["requiredExposures"] else None


def _next_available_load(slot: JSON, baseline_load: float) -> float | None:
    """The smallest confirmed equipment step above the baseline, unchanged in type."""
    for candidate in sorted(slot["equipment"]["availableLoads"]):
        if candidate > baseline_load + LOAD_EPSILON:
            return candidate  # type: ignore[no-any-return]
    return None
