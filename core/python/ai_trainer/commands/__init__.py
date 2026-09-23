"""State commands: every mutation of AthleteState, as a pure reducer.

The host sends ``{command, arguments, state, library, now, ids}``. The reducer
deep-copies ``state``, applies exactly one command, and returns the candidate
state (plus an optional boolean ``value``). The host saves the candidate
atomically and only then publishes it; the state ``revision`` is incremented by
the host on durable commit, never here.

Command handlers are grouped by concern:

- ``plan``     — acceptInitialPlan, configureLoad
- ``workout``  — start, skip, setPaused, saveSet, finish, reportPain, exclude
- ``records``  — correctSet, resolveConflict, deleteSession
- ``meals``    — saveMeal, deleteMeal
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from ..errors import DomainError
from . import meals, plan, records, workout
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
    "deleteMeal": meals.delete_meal,
    "saveMeal": meals.save_meal,
}


def reduce_state(payload: JSON) -> JSON:
    """Apply one command to a copy of the payload's state and return ``{state, value?}``."""
    handler = HANDLERS.get(payload["command"])
    if handler is None:
        raise DomainError("unsupported")
    context = CommandContext(
        state=deepcopy(payload["state"]),
        arguments=deepcopy(payload.get("arguments", {})),
        library=payload["library"],
        now=payload["now"],
        ids=iter(payload["ids"]),
    )
    value = handler(context)
    result: JSON = {"state": context.state}
    if value is not None:
        result["value"] = value
    return result


__all__ = ["HANDLERS", "CommandContext", "reduce_state"]
