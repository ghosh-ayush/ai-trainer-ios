"""Diet commands: accept targets, weigh-ins, adjustments, and meals logged from the food table.

Targets change only when the athlete accepts them (AGENTS.md rule 3): ``setDietTargets``
and ``acceptDietAdjustment`` recompute the suggestion from the stored state and require it
to match what the athlete saw, exactly as training acceptance does.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from .. import diet, diet_content, foods
from ..errors import DomainError, require
from .context import CommandContext

JSON = dict[str, Any]

WEIGH_IN_SOURCES = ("manual", "appleHealth")
# A body mass outside this range is a typing or unit error, not a measurement.
PLAUSIBLE_KG = (25.0, 400.0)
COMPARED_TARGET_FIELDS = ("energyKcal", "proteinG", "carbohydrateG", "fatG", "fibreG", "policyVersion")


def set_diet_targets(context: CommandContext) -> None:
    """Store the profile and the targets it produces, if they match what the athlete accepted."""
    policy = _policy()
    profile = deepcopy(context.arguments["profile"])
    diet.validate_profile(profile, policy, context.now)
    require(
        diet.safety_block(profile, context.now, policy, context.state["weighIns"]) is None,
        "invalid",
        "Diet targets are withheld for your answers. Save your answers instead.",
    )
    weight = diet.current_weight(context.state["weighIns"], context.now, policy, diet.pace_of(profile, policy))
    if weight is None:
        raise DomainError("invalid", "Log your body weight first.")
    basis = "profileChange" if context.state.get("dietTargets") else "setup"
    targets, notes = diet.targets_for(profile, weight, context.now, policy, basis)
    require("FAT_LOSS_NOT_AVAILABLE" not in notes, "invalid", "Fat loss is not available at your safe energy floor.")
    _require_same(targets, context.arguments["expected"])
    current = context.state.get("dietTargets")
    if current is not None and all(current[field] == targets[field] for field in COMPARED_TARGET_FIELDS):
        # Same numbers (a new pace, cuisine or diet type): keep the targets and their date, so
        # the adaptation window is not restarted by a change that does not affect energy.
        context.state["dietProfile"] = profile
        context.record("diet_profile_saved", reason="targetsUnchanged")
        return
    context.state["dietProfile"] = profile
    context.state["dietTargets"] = targets
    context.state["dietDecisions"].append(_decision(context, basis, targets, "PROFILE_ACCEPTED", "applied"))
    context.record("diet_targets_set", reason=basis)


def save_diet_profile(context: CommandContext) -> None:
    """Store the athlete's answers without accepting targets; answers that withhold targets remove them.

    Safety answers must always be savable: someone who reports a pregnancy or a condition after
    accepting targets must stop seeing them at once (diet-1 ``safety.exclusions``).
    """
    policy = _policy()
    profile = deepcopy(context.arguments["profile"])
    diet.validate_profile(profile, policy, context.now)
    context.state["dietProfile"] = profile
    block = diet.safety_block(profile, context.now, policy, context.state["weighIns"])
    if block is not None and context.state.get("dietTargets") is not None:
        withdrawn = context.state.pop("dietTargets")
        context.state["dietDecisions"].append(_decision(context, "withheld", withdrawn, block, "expired"))
    context.record("diet_profile_saved", reason=block)


def log_weigh_in(context: CommandContext) -> None:
    """Add one weigh-in the athlete typed or granted from Apple Health."""
    weigh_in = deepcopy(context.arguments["weighIn"])
    _validate_weigh_in(weigh_in, context.now)
    require(
        all(w["id"] != weigh_in["id"] for w in context.state["weighIns"]), "invalid", "That weigh-in already exists."
    )
    context.state["weighIns"].append(weigh_in)
    context.state["weighIns"].sort(key=lambda w: w["measuredAt"])
    context.record("weigh_in_logged", reason=weigh_in["source"])


def import_weigh_ins(context: CommandContext) -> bool:
    """Add Apple Health weigh-ins; True if any were new.

    Skips samples already stored at the same instant, samples the athlete deleted before, and
    implausible readings (another person on a shared scale, a failed reading), so one bad
    sample never blocks the rest.
    """
    existing = {(w["source"], w["measuredAt"]) for w in context.state["weighIns"]}
    excluded = set(context.state["excludedWeighIns"])
    added = 0
    for weigh_in in context.arguments["weighIns"]:
        weigh_in = deepcopy(weigh_in)
        require(weigh_in["source"] == "appleHealth", "invalid", "Only Apple Health weigh-ins can be imported.")
        if (weigh_in["source"], weigh_in["measuredAt"]) in existing or weigh_in["measuredAt"] in excluded:
            continue
        if not _plausible(weigh_in, context.now):
            continue
        existing.add((weigh_in["source"], weigh_in["measuredAt"]))
        context.state["weighIns"].append(weigh_in)
        added += 1
    context.state["weighIns"].sort(key=lambda w: w["measuredAt"])
    if added:
        context.record("weigh_ins_imported")
    return added > 0


def delete_weigh_in(context: CommandContext) -> None:
    """Remove one weigh-in; the trend is recomputed from what remains.

    A deleted Apple Health sample is remembered, so the next import does not bring it back.
    """
    weigh_in_id = context.arguments["id"]
    found = next((w for w in context.state["weighIns"] if w["id"] == weigh_in_id), None)
    if found is None:
        raise DomainError("notFound")
    context.state["weighIns"] = [w for w in context.state["weighIns"] if w["id"] != weigh_in_id]
    if found["source"] == "appleHealth" and found["measuredAt"] not in context.state["excludedWeighIns"]:
        context.state["excludedWeighIns"].append(found["measuredAt"])


def accept_diet_adjustment(context: CommandContext) -> None:
    """Apply the suggested adjustment, re-evaluated now, if it is the one the athlete accepted."""
    adjustment = _current_adjustment(context)
    _require_same(adjustment["targets"], context.arguments["expected"])
    context.state["dietTargets"] = adjustment["targets"]
    context.state["dietDecisions"].append(
        _decision(context, "adjustment", adjustment["targets"], adjustment["reason"], "applied")
    )
    context.record("diet_adjustment_accepted", reason=adjustment["reason"])


def reject_diet_adjustment(context: CommandContext) -> None:
    """Keep the current targets; no new suggestion until the policy's waiting period passes."""
    adjustment = _current_adjustment(context)
    _require_same(adjustment["targets"], context.arguments["expected"])
    context.state["dietDecisions"].append(
        _decision(context, "adjustment", adjustment["targets"], adjustment["reason"], "rejected")
    )
    context.record("diet_adjustment_rejected", reason=adjustment["reason"])


def save_food_meal(context: CommandContext) -> None:
    """Log grams of a bundled USDA food; the nutrients come from the table, never from the host."""
    arguments = context.arguments
    grams = arguments["grams"]
    require(
        isinstance(grams, (int, float)) and not isinstance(grams, bool) and math.isfinite(grams) and 0 < grams <= 5000,
        "invalid",
        "Enter a portion between 1 and 5000 g.",
    )
    item = foods.food(arguments["foodID"])
    require(
        all(meal["id"] != arguments["id"] for meal in context.state["meals"]), "invalid", "That meal already exists."
    )
    context.state["meals"].append(
        {
            "id": arguments["id"],
            "revision": 1,
            "name": f"{item['name']} ({grams:g} g)",
            "nutrients": foods.nutrients_per(item, float(grams)),
            "occurredAt": arguments["occurredAt"],
            "source": f"fdc:{item['id']}",
            "timeZone": arguments["timeZone"],
        }
    )
    context.record("meal_saved", occurred_at=arguments["occurredAt"])


def _current_adjustment(context: CommandContext) -> JSON:
    adjustment = diet.adjustment_for(context.state, context.now, _policy())
    if adjustment is None:
        raise DomainError("staleProposal", "That suggestion no longer applies. Review your diet again.")
    return adjustment


def _require_same(computed: JSON, expected: JSON) -> None:
    if any(computed[field] != expected[field] for field in COMPARED_TARGET_FIELDS):
        raise DomainError("staleProposal", "Your targets changed since you saw them. Review them again.")


def _decision(context: CommandContext, kind: str, targets: JSON, reason: str, status: str) -> JSON:
    return {
        "id": context.next_id(),
        "kind": kind,
        "targets": targets,
        "reason": reason,
        "decidedAt": context.now,
        "status": status,
    }


def _policy() -> JSON:
    policy = diet_content.active_policy()
    if policy is None:
        raise DomainError("unsupported", "No diet evidence bundle is available in this build.")
    return policy


def _plausible(weigh_in: JSON, now: float) -> bool:
    kg = weigh_in["kg"]
    return (
        isinstance(kg, (int, float))
        and not isinstance(kg, bool)
        and math.isfinite(kg)
        and PLAUSIBLE_KG[0] <= kg <= PLAUSIBLE_KG[1]
        and weigh_in["measuredAt"] <= now + 300
    )


def _validate_weigh_in(weigh_in: JSON, now: float) -> None:
    require(weigh_in["source"] in WEIGH_IN_SOURCES, "invalid", "Unknown weigh-in source.")
    require(weigh_in["measuredAt"] <= now + 300, "invalid", "A weigh-in cannot be in the future.")
    require(_plausible(weigh_in, now), "invalid", "Enter a weight between 25 and 400 kg (55-880 lb).")
