"""P4 nutrition commands: user-confirmed estimates with an audit trail."""

from __future__ import annotations

from copy import deepcopy

from ..errors import require
from ..nutrition import validate_nutrients
from .context import CommandContext


def save_meal(context: CommandContext) -> None:
    """Create a meal, or correct an existing one when the caller holds its current revision."""
    state = context.state
    meal = deepcopy(context.arguments["meal"])
    validate_nutrients(meal["nutrients"])
    require(bool(meal["name"].strip()), "invalid", "Give this meal a name.")
    existing = next((candidate for candidate in state["meals"] if candidate["id"] == meal["id"]), None)
    if existing is not None:
        require(meal["revision"] == existing["revision"])
        state["mealAudits"].append(
            {"id": context.next_id(), "previous": deepcopy(existing), "correctedAt": context.now}
        )
        meal["revision"] = existing["revision"] + 1
        state["meals"][state["meals"].index(existing)] = meal
    else:
        state["meals"].append(meal)
    if context.arguments["asRecipe"]:
        state["recipes"].append(
            {"id": context.next_id(), "name": meal["name"], "perServing": meal["nutrients"], "source": "user_estimate"}
        )
    context.record("meal_saved", occurred_at=meal["occurredAt"])


def delete_meal(context: CommandContext) -> None:
    """Remove a meal and its correction records. Saved recipes are separate and stay."""
    state = context.state
    meal_id = context.arguments["id"]
    state["meals"] = [meal for meal in state["meals"] if meal["id"] != meal_id]
    state["mealAudits"] = [audit for audit in state["mealAudits"] if audit["previous"]["id"] != meal_id]
