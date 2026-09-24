"""What the Diet tab shows, as read-only queries over state and the active diet policy.

``diet_view`` is the tab model: status (ready, needs input, withheld), accepted targets,
what was eaten today and what is left, the weight trend, at most one suggested adjustment,
food ideas, and the citations behind every number. ``diet_preview`` is the same model for a
profile the athlete has not accepted yet. ``diet_options`` is what the setup screen offers.
"""

from __future__ import annotations

from typing import Any

from . import diet, diet_content, foods

JSON = dict[str, Any]

EMPTY_NUTRIENTS = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

WITHHELD_MESSAGES = {
    "underMinimumAge": "Diet targets are for adults only.",
    "pregnancy": (
        "During pregnancy, energy needs are individual. "
        "Please plan your diet with your clinician or a registered dietitian."
    ),
    "lactation": (
        "While breastfeeding, energy needs are individual. "
        "Please plan your diet with your clinician or a registered dietitian."
    ),
    "eatingDisorderRisk": (
        "Your answers suggest calorie targets may not be right for you now. "
        "Please talk to a clinician or a registered dietitian; the app will not set targets."
    ),
    "eatingDisorderHistory": (
        "With an eating disorder now or in the past, calorie targets should come from your care team. "
        "The app will not set them."
    ),
    "lowBmi": (
        "Your weight is in a range where the app will not set diet targets. "
        "Please talk to a clinician or a registered dietitian."
    ),
    "lowBmiForFatLoss": (
        "Fat loss is not offered at your current weight. Choose maintenance, muscle gain or endurance instead."
    ),
    "rapidRecentWeightLoss": (
        "You have lost weight quickly this month, so the app will not set diet targets now. Please talk to a clinician."
    ),
    "fatLossNotAvailable": (
        "Fat loss is not available: your lowest safe energy is at or above what you are estimated to need. "
        "Choose maintenance or another goal."
    ),
}
# Exclusions the core computes or asks about separately, so the setup screen does not list them as conditions.
COMPUTED_EXCLUSIONS = frozenset(
    {"underMinimumAge", "pregnancy", "lactation", "eatingDisorderRisk", "lowBmi", "rapidRecentWeightLoss"}
)
DEFAULT_WITHHELD = "A condition you reported needs a clinician's plan. The app will not set diet targets for you."

NOTE_COPY = {
    "ENERGY_AT_SAFETY_FLOOR": (
        "Energy is at the lowest level the evidence supports for you; the goal rate may be slower."
    ),
    "ENERGY_RAISED_FOR_CARBOHYDRATE": "Energy is higher than your estimated need so training carbohydrate fits.",
    "ENERGY_RAISED_FOR_CARBOHYDRATE_FLOOR": "Energy is set so carbohydrate stays at its minimum.",
}


def diet_view(state: JSON, now: float, day_start: float | None) -> JSON:
    """The Diet tab for the accepted profile and targets."""
    policy = diet_content.active_policy()
    profile = state.get("dietProfile")
    if policy is None:
        return _status("withheld", "NO_DIET_POLICY", "No diet evidence bundle is available in this build.", "")
    if profile is None:
        return _status(
            "needsInput",
            "NO_DIET_PROFILE",
            "Answer a few questions about you, your goal and how you eat to get daily targets.",
            policy["version"],
        )
    block = diet.safety_block(profile, now, policy, state["weighIns"])
    if block is not None:
        return _status("withheld", block, WITHHELD_MESSAGES.get(block, DEFAULT_WITHHELD), policy["version"])
    targets = state.get("dietTargets")
    if targets is None:
        return _status("needsInput", "NO_DIET_TARGETS", "Review and accept your daily targets.", policy["version"])
    eaten = eaten_today(state, now, day_start)
    remaining = {
        "calories": round(targets["energyKcal"] - eaten["calories"], 1),
        "protein": round(targets["proteinG"] - eaten["protein"], 1),
        "carbs": round(targets["carbohydrateG"] - eaten["carbs"], 1),
        "fat": round(targets["fatG"] - eaten["fat"], 1),
    }
    view = _status("ready", "TARGETS_ACCEPTED", "", policy["version"])
    view.update(
        {
            "targets": targets,
            "eaten": eaten,
            "remaining": remaining,
            "suggestions": foods.suggest(remaining, targets, profile, policy),
            "citations": citations(),
            "notes": notes_for(profile, policy),
        }
    )
    trend = diet.weight_trend(state["weighIns"], now, policy, pace=diet.pace_of(profile, policy))
    if trend is not None:
        view["trend"] = trend
    adjustment = diet.adjustment_for(state, now, policy)
    if adjustment is not None:
        view["adjustment"] = adjustment
    return view


def diet_preview(state: JSON, profile: JSON, now: float) -> JSON:
    """What accepting ``profile`` would set, at the latest weigh-in in ``state``."""
    policy = diet_content.active_policy()
    if policy is None:
        return _status("withheld", "NO_DIET_POLICY", "No diet evidence bundle is available in this build.", "")
    diet.validate_profile(profile, policy, now)
    block = diet.safety_block(profile, now, policy, state["weighIns"])
    if block is not None:
        return _status("withheld", block, WITHHELD_MESSAGES.get(block, DEFAULT_WITHHELD), policy["version"])
    weight = diet.current_weight(state["weighIns"], now, policy, diet.pace_of(profile, policy))
    if weight is None:
        return _status(
            "needsInput", "NO_WEIGH_IN", "Log your body weight first; targets are never guessed.", policy["version"]
        )
    basis = "profileChange" if state.get("dietTargets") else "setup"
    targets, notes = diet.targets_for(profile, weight, now, policy, basis)
    if "FAT_LOSS_NOT_AVAILABLE" in notes:
        return _status("withheld", "fatLossNotAvailable", WITHHELD_MESSAGES["fatLossNotAvailable"], policy["version"])
    view = _status("ready", "PREVIEW", "", policy["version"])
    view.update(
        {
            "targets": targets,
            "notes": [NOTE_COPY[note] for note in notes] + notes_for(profile, policy),
            "citations": citations(),
        }
    )
    return view


def notes_for(profile: JSON, policy: JSON) -> list[str]:
    """What the athlete should know about their targets: estimate error, logged intake, nutrients to watch."""
    error = policy["energy"]["predictionErrorKcal"][profile["sex"]]
    notes = [
        f"Energy comes from the NASEM 2023 equations, which are typically within about {error:g} kcal a day for one "
        "person. Your weigh-ins correct it over time.",
        policy["adaptation"]["intakeNote"],
    ]
    if profile["pattern"] in ("vegetarian", "vegan"):
        nutrients = list(policy["patterns"][profile["pattern"]]["nutrientsOfConcern"])
        notes.append(f"On a {profile['pattern']} diet, plan for {', '.join(nutrients)} (see Why these numbers).")
    return notes


def diet_options() -> JSON:
    """The choices the setup screen offers, from the active policy."""
    policy = diet_content.active_policy()
    if policy is None:
        return {
            "activityLevels": [],
            "goals": [],
            "patterns": [],
            "cuisines": [],
            "trainingLoads": [],
            "exclusions": [],
            "scoffQuestions": [],
            "minimumAgeYears": 18,
            "paces": [],
            "defaultPace": "standard",
            "paceQuestion": "",
            "paceNote": "",
            "policyVersion": "",
        }
    loads = policy["goals"]["endurance"]["carbohydrateGPerKgByTrainingLoad"]
    return {
        "activityLevels": [
            {"id": level["id"], "title": level["title"], "detail": level["description"]}
            for level in policy["energy"]["activityLevels"]
        ],
        "goals": [{"id": goal, "title": title, "detail": detail} for goal, title, detail in GOAL_COPY],
        "patterns": [{"id": p, "title": title, "detail": detail} for p, title, detail in PATTERN_COPY],
        "cuisines": [{"id": c, "title": title, "detail": ""} for c, title in CUISINE_COPY],
        "trainingLoads": [
            {"id": load, "title": LOAD_TITLES[load], "detail": f"{low:g}-{high:g} g carbohydrate per kg a day"}
            for load, (low, high) in loads.items()
        ],
        "exclusions": [
            {"id": exclusion["id"], "title": exclusion["title"], "detail": exclusion["description"]}
            for exclusion in policy["safety"]["exclusions"]
            if exclusion["id"] not in COMPUTED_EXCLUSIONS
        ],
        "scoffQuestions": list(policy["safety"]["scoff"]["questions"]),
        "minimumAgeYears": int(policy["safety"]["minimumAgeYears"]),
        "paces": [
            {"id": pace, "title": PACE_TITLES[pace], "detail": policy["adaptation"]["paceCopy"][pace]}
            for pace in PACE_TITLES
            if pace in policy["adaptation"]["paces"]
        ],
        "defaultPace": policy["adaptation"]["defaultPace"],
        "paceQuestion": policy["adaptation"]["paceCopy"]["question"],
        "paceNote": policy["adaptation"]["paceCopy"]["perceivedMetabolismNote"],
        "policyVersion": policy["version"],
    }


GOAL_COPY = (
    ("fatLoss", "Fat loss", "A steady deficit that protects muscle."),
    ("muscleGain", "Muscle gain", "A small surplus with high protein."),
    ("maintenance", "Maintain / recomposition", "Hold your weight while you train."),
    ("endurance", "Endurance fuelling", "Carbohydrate matched to your training load."),
)
PATTERN_COPY = (
    ("omnivore", "No restrictions", "Any food."),
    ("vegetarian", "Vegetarian", "No meat or fish; dairy and eggs are fine."),
    ("vegan", "Vegan", "No animal products."),
)
CUISINE_COPY = (
    ("indian", "Indian"),
    ("mexican", "Mexican"),
    ("chinese", "Chinese"),
    ("japanese", "Japanese"),
    ("korean", "Korean"),
    ("southeastAsian", "Thai / Vietnamese"),
    ("italian", "Italian"),
    ("mediterranean", "Mediterranean"),
)
LOAD_TITLES = {"light": "Light", "moderate": "Moderate", "high": "High", "veryHigh": "Very high"}
PACE_TITLES = {"standard": "Standard", "slower": "Slower, most certain"}


def eaten_today(state: JSON, now: float, day_start: float | None) -> JSON:
    """Logged meals on the athlete's local day, including ones timed later today (the last 24 hours if unknown)."""
    start, end = (day_start, day_start + diet.DAY) if day_start is not None else (now - diet.DAY, now + 1)
    totals = dict(EMPTY_NUTRIENTS)
    for meal in state["meals"]:
        if start <= meal["occurredAt"] < end:
            for key in totals:
                totals[key] += meal["nutrients"][key]
    return {key: round(value, 1) for key, value in totals.items()}


def citations() -> list[JSON]:
    """Every value of the active diet policy with the research behind it."""
    sources = diet_content.active_sources()
    shown = []
    for path, node in diet_content.active_citations():
        if node["source"] == "owner":
            citation, locator, certainty = f"No study gives this number. {node['rationale']}", "", "owner decision"
        else:
            citation = sources[node["source"]]["citation"]
            locator, certainty = node["locator"], node["certainty"]
        shown.append(
            {
                "parameter": path.removeprefix("policy."),
                "value": _short(node["value"]),
                "citation": citation,
                "locator": locator,
                "certainty": certainty,
            }
        )
    return shown


def _short(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (list, dict)):
        text = str(value)
        return text if len(text) <= 80 else text[:77] + "..."
    return str(value)


def _status(status: str, reason: str, message: str, version: str) -> JSON:
    return {
        "status": status,
        "reason": reason,
        "message": message,
        "eaten": dict(EMPTY_NUTRIENTS),
        "suggestions": [],
        "notes": [],
        "citations": [],
        "policyVersion": version,
    }
