"""Commands that establish or configure the accepted plan."""

from __future__ import annotations

import math

from ..athlete_state import has_active_session, next_plan
from ..errors import require
from ..events import store_plan
from ..rules.program import REQUIRED_ID_COUNT, initial_program
from .context import CommandContext


def accept_initial_plan(context: CommandContext) -> None:
    """Replace the current program with a freshly selected one for ``profile``.

    The previous program is retained in ``previousPrograms`` so completed
    sessions keep their provenance (AS-07).
    """
    state = context.state
    profile = context.arguments["profile"]
    program_ids = [context.next_id() for _ in range(REQUIRED_ID_COUNT)]
    program = initial_program(profile, context.library, context.now, program_ids)
    require(not has_active_session(state), "invalid", "End the active session before changing programs.")
    if state.get("program"):
        state["previousPrograms"].append(state["program"])
    state["profile"] = profile
    state["program"] = program
    state.pop("nextPlanOverride", None)
    context.mark_context_changed()
    context.record("plan_accepted")


def configure_load(context: CommandContext) -> None:
    """Set the athlete's confirmed working load and available equipment steps for one slot."""
    state = context.state
    load = context.arguments.get("load")
    options = context.arguments["options"]
    require(
        (load is None or (math.isfinite(load) and load >= 0))
        and all(math.isfinite(step) and step >= 0 for step in options),
        "invalid",
        "Loads must be finite, nonnegative numbers.",
    )
    plan = next_plan(state)
    require(not has_active_session(state) and plan is not None)
    assert plan is not None
    slot = next((candidate for candidate in plan["slots"] if candidate["id"] == context.arguments["slotID"]), None)
    require(slot is not None)
    assert slot is not None
    slot.pop("load", None)
    if load is not None:
        slot["load"] = load
    slot["equipment"]["availableLoads"] = sorted(set(options))
    plan["revision"] += 1
    store_plan(plan, state)
    context.mark_context_changed()
