"""State commands: every mutation of AthleteState, as a pure reducer.

The host sends ``{command, arguments, state, permitsFixtures, now, ids}``. The
payload belongs to this call — ``dispatch_json`` has just parsed it — so the
reducer applies exactly one command to that state in place (no copy of a
multi-megabyte history per tap) and returns it as the candidate state (plus an
optional boolean ``value`` or ``decision``). The host
saves the candidate atomically and only then publishes it; the state
``revision`` is incremented by the host on durable commit, never here.

Command handlers are grouped by concern:

- ``plan``      — acceptInitialPlan, configureLoad
- ``workout``   — start, skip, setPaused, saveSet, finish, reportPain, exclude
- ``records``   — correctSet, resolveConflict, deleteSession
- ``meals``     — saveMeal, deleteMeal
- ``proposals`` — requestChange, acceptRecommendation, rejectRecommendation
- ``diet``      — setDietTargets, saveDietProfile, logWeighIn, importWeighIns, deleteWeighIn,
                  acceptDietAdjustment, rejectDietAdjustment, saveFoodMeal
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..errors import DomainError
from . import diet, meals, plan, proposals, records, status, workout
from .context import CommandContext

JSON = dict[str, Any]
Handler = Callable[[CommandContext], "bool | None"]

HANDLERS: dict[str, Handler] = {
    "acceptInitialPlan": plan.accept_initial_plan,
    "configureLoad": plan.configure_load,
    "start": workout.start,
    "skip": workout.skip,
    "setPaused": workout.set_paused,
    "saveSet": workout.save_set,
    "finish": workout.finish,
    "reportPain": workout.report_pain,
    "exclude": workout.exclude,
    "correctSet": records.correct_set,
    "resolveConflict": records.resolve_conflict,
    "deleteSession": records.delete_session,
    "setStatus": status.set_status,
    "endStatus": status.end_status,
    "deleteMeal": meals.delete_meal,
    "saveMeal": meals.save_meal,
    "requestChange": proposals.request_change,
    "acceptRecommendation": proposals.accept,
    "rejectRecommendation": proposals.reject,
    "setDietTargets": diet.set_diet_targets,
    "saveDietProfile": diet.save_diet_profile,
    "logWeighIn": diet.log_weigh_in,
    "importWeighIns": diet.import_weigh_ins,
    "deleteWeighIn": diet.delete_weigh_in,
    "acceptDietAdjustment": diet.accept_diet_adjustment,
    "rejectDietAdjustment": diet.reject_diet_adjustment,
    "saveFoodMeal": diet.save_food_meal,
}


def reduce_state(payload: JSON, library: JSON) -> JSON:
    """Apply one command to the payload's state and return ``{state, value?, decision?}``.

    The payload is consumed: pass one you own (as ``dispatch`` does), not a shared object.
    """
    handler = HANDLERS.get(payload["command"])
    if handler is None:
        raise DomainError("unsupported")
    context = CommandContext(
        state=payload["state"],
        arguments=payload.get("arguments", {}),
        library=library,
        now=payload["now"],
        ids=iter(payload["ids"]),
    )
    value = handler(context)
    result: JSON = {"state": context.state}
    if value is not None:
        result["value"] = value
    if context.decision is not None:
        result["decision"] = context.decision
    return result


__all__ = ["HANDLERS", "CommandContext", "reduce_state"]
