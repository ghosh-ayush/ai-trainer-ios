"""Training status (ADR-019): the athlete marks a break, an illness or an injury.

While a status is active, the app stops proposing changes on its own (progression, a week fitted
to attendance), and the status days do not count as missed sessions. Anything the athlete asks
for themselves (a shorter session, a swap, a new day) still works. A status never diagnoses and
never changes the plan: it only pauses what the app would otherwise suggest.
"""

from __future__ import annotations

from ..athlete_state import active_status
from ..errors import require
from .context import CommandContext


def set_status(context: CommandContext) -> None:
    """Start a status, ending any current one. ``endsAt`` is optional; without it, it lasts until ended."""
    state = context.state
    ends_at = context.arguments.get("endsAt")
    require(ends_at is None or ends_at > context.now, "invalid", "Choose an end after now.")
    current = active_status(state, context.now)
    if current is not None:
        current["endedAt"] = context.now
    period = {"id": context.next_id(), "kind": context.arguments["status"], "startedAt": context.now}
    if ends_at is not None:
        period["endsAt"] = ends_at
    state["statusPeriods"].append(period)
    context.expire_proposals()
    context.mark_context_changed()
    context.record("status_set", context.arguments["status"])


def end_status(context: CommandContext) -> None:
    """End the active status now ("I'm back")."""
    current = active_status(context.state, context.now)
    require(current is not None, "invalid", "There is no break, illness or injury to end.")
    assert current is not None
    current["endedAt"] = context.now
    context.expire_proposals()
    context.mark_context_changed()
    context.record("status_ended", current["kind"])
