"""The diet engine: daily energy and macro targets, the weight trend, and adaptive adjustments.

Every number comes from the active diet policy (``diet_content``), which cites research for
each value (AGENTS.md rule 1). The functions here are pure: they take the policy as an
argument, never read files, and never mutate state.

- ``targets_for`` turns a diet profile and a body weight into daily targets: total energy
  from the policy's published equation (NASEM 2023 DRI EER), shifted by the goal's weekly
  rate of change, bounded by the safety floors; protein by goal, fat within its energy
  range, carbohydrate as the remainder (or by training load for endurance).
- ``weight_trend`` fits a least-squares line through the weigh-ins in the policy window.
- ``adjustment_for`` compares that trend with the goal's rate and suggests one step up or
  down. It is only a suggestion: nothing changes until the athlete accepts (rule 3).
- ``safety_block`` withholds targets entirely for the people the policy excludes.

Unknown stays unknown (rule 2): with no weigh-in there are no targets, body fat is used
only when the athlete gave it, and logged intake is shown but never treated as exact.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from .errors import require

JSON = dict[str, Any]

DAY = 86_400.0
WEEK_DAYS = 7.0
KILOGRAMS_PER_POUND = 0.45359237  # unit conversion for display copy only
CUISINES = ("indian", "mexican", "chinese", "japanese", "korean", "southeastAsian", "italian", "mediterranean")
# Foundation reference date (2001-01-01) as days since 1970-01-01, for calendar arithmetic
# without ``datetime``, which the embedded iOS runtime does not ship.
_REFERENCE_EPOCH_DAYS = 11_323


def pace_of(profile: JSON | None, policy: JSON) -> str:
    """The athlete's adaptation pace, or the policy's default when they have not chosen one."""
    chosen = (profile or {}).get("pace")
    return str(
        chosen if chosen in parameter(policy, "adaptation.paces") else parameter(policy, "adaptation.defaultPace")
    )


def pace_parameter(policy: JSON, pace: str, name: str) -> Any:
    """One adaptation value for ``pace`` (window, weigh-ins, tolerance, step, waiting period)."""
    return parameter(policy, f"adaptation.paces.{pace}.{name}")


def parameter(policy: JSON, path: str) -> Any:
    """The resolved policy value at dotted ``path`` (``"goals.fatLoss.weeklyChangeFraction"``)."""
    node: Any = policy
    for key in path.split("."):
        node = node[key]
    return node


# --- safety -------------------------------------------------------------------------------


def safety_block(profile: JSON, now: float, policy: JSON, weigh_ins: Sequence[JSON] = ()) -> str | None:
    """The exclusion id that withholds targets for this athlete, or None when none applies.

    Self-reported answers come first; then what the weigh-ins show whether or not the athlete
    ticked a box: a very low BMI, a fat-loss goal below the fat-loss BMI floor, or a rapid
    recent loss (diet-1 ``safety``).
    """
    if age_years(profile["birthYear"], now) < parameter(policy, "safety.minimumAgeYears"):
        return "underMinimumAge"
    excluded = {exclusion["id"] for exclusion in parameter(policy, "safety.exclusions")}
    screening = profile["screening"]
    if screening["pregnant"] and "pregnancy" in excluded:
        return "pregnancy"
    if screening["lactating"] and "lactation" in excluded:
        return "lactation"
    if sum(1 for answer in screening["scoffAnswers"] if answer) >= parameter(policy, "safety.scoff.referralScore"):
        return "eatingDisorderRisk"
    for condition in screening["conditions"]:
        if condition in excluded:
            return str(condition)
    weight = current_weight(weigh_ins, now, policy, pace_of(profile, policy))
    if weight is not None:
        bmi = weight / (profile["heightCm"] / 100) ** 2
        if bmi <= parameter(policy, "safety.minimumBMI"):
            return "lowBmi"
        if profile["goal"] == "fatLoss" and bmi < parameter(policy, "safety.fatLossMinimumBMI"):
            return "lowBmiForFatLoss"
    if rapid_recent_loss(weigh_ins, now, policy):
        return "rapidRecentWeightLoss"
    return None


def validate_profile(profile: JSON, policy: JSON, now: float) -> None:
    """Refuse a profile the equations cannot use; the same check runs for a preview and for acceptance."""
    require(100 <= profile["heightCm"] <= 250, "invalid", "Enter your height in centimetres (100-250).")
    require(1900 <= profile["birthYear"] <= calendar_year(now), "invalid", "Enter your birth year.")
    body_fat = profile.get("bodyFatPercent")
    require(body_fat is None or 3 <= body_fat <= 70, "invalid", "Body fat must be between 3 and 70 percent.")
    questions = parameter(policy, "safety.scoff.questions")
    require(len(profile["screening"]["scoffAnswers"]) == len(questions), "invalid", "Answer every screening question.")
    known = {exclusion["id"] for exclusion in parameter(policy, "safety.exclusions")}
    require(
        all(condition in known for condition in profile["screening"]["conditions"]), "invalid", "Unknown condition."
    )
    require(all(cuisine in CUISINES for cuisine in profile["cuisines"]), "invalid", "Unknown cuisine.")
    if profile["goal"] == "endurance":
        require(profile.get("trainingLoad") is not None, "invalid", "Choose your training load for endurance fuelling.")


def rapid_recent_loss(weigh_ins: Sequence[JSON], now: float, policy: JSON) -> bool:
    """True when the latest weigh-in is at least the policy's fraction below the heaviest in its window."""
    days = parameter(policy, "safety.rapidLossDays")
    recent = [w for w in daily_weigh_ins(weigh_ins) if now - days * DAY <= w["measuredAt"] <= now]
    if len(recent) < 2:
        return False
    heaviest = max(w["kg"] for w in recent)
    return bool((heaviest - recent[-1]["kg"]) / heaviest >= parameter(policy, "safety.rapidLossFraction"))


def age_years(birth_year: int, now: float) -> int:
    """Whole years between ``birth_year`` and the calendar year of ``now`` (reference-epoch seconds)."""
    return calendar_year(now) - birth_year


def calendar_year(seconds_since_2001: float) -> int:
    """The UTC calendar year of a Foundation reference-epoch timestamp (civil-from-days)."""
    days = int(seconds_since_2001 // DAY) + _REFERENCE_EPOCH_DAYS + 719_468
    era = days // 146_097
    day_of_era = days - era * 146_097
    year_of_era = (day_of_era - day_of_era // 1_460 + day_of_era // 36_524 - day_of_era // 146_096) // 365
    day_of_year = day_of_era - (365 * year_of_era + year_of_era // 4 - year_of_era // 100)
    month_index = (5 * day_of_year + 2) // 153
    month = month_index + 3 if month_index < 10 else month_index - 9
    return year_of_era + era * 400 + (1 if month <= 2 else 0)


# --- energy and macros --------------------------------------------------------------------


def estimated_energy_requirement(profile: JSON, weight_kg: float, now: float, policy: JSON) -> float:
    """Daily total energy expenditure (kcal) from the policy's EER equation for sex and activity."""
    coefficients = parameter(policy, "energy.eerCoefficients")[profile["sex"]][profile["activity"]]
    return float(
        coefficients["intercept"]
        + coefficients["age"] * age_years(profile["birthYear"], now)
        + coefficients["heightCm"] * profile["heightCm"]
        + coefficients["weightKg"] * weight_kg
    )


def energy_floor(profile: JSON, weight_kg: float, requirement: float, policy: JSON) -> float:
    """The lowest daily energy the app will ever set for this athlete (kcal)."""
    floors = [
        parameter(policy, "safety.minimumEnergyKcal")[profile["sex"]],
        requirement * (1 - parameter(policy, "safety.maximumDeficitFractionOfTEE")),
    ]
    body_fat = profile.get("bodyFatPercent")
    if body_fat is not None:
        # Energy availability = (intake - exercise energy) / FFM. Without a measured exercise
        # expenditure the floor assumes none, so it is the least the athlete may eat.
        fat_free_mass = weight_kg * (1 - body_fat / 100)
        floors.append(parameter(policy, "safety.energyAvailabilityFloorKcalPerKgFFM") * fat_free_mass)
    return float(max(floors))


def targets_for(profile: JSON, weight_kg: float, now: float, policy: JSON, basis: str) -> tuple[JSON, list[str]]:
    """Daily targets for ``profile`` at ``weight_kg`` and the notes that explain any bound applied."""
    notes: list[str] = []
    requirement = estimated_energy_requirement(profile, weight_kg, now, policy)
    goal = profile["goal"]
    weekly_fraction = parameter(policy, f"goals.{goal}.weeklyChangeFraction")
    offset = weekly_fraction * weight_kg * parameter(policy, "energy.tissueKcalPerKgBodyMass") / WEEK_DAYS
    energy = requirement + offset
    floor = energy_floor(profile, weight_kg, requirement, policy)
    if energy < floor:
        energy = floor
        notes.append("ENERGY_AT_SAFETY_FLOOR")
    targets = macros_for(energy, profile, weight_kg, now, policy, basis, notes, floor=floor)
    if goal == "fatLoss" and targets["energyKcal"] >= requirement:
        # The floor sits at or above the estimated need: no deficit is possible, so this
        # would be a maintenance or surplus target labelled fat loss (diet-1 safety notes).
        notes.append("FAT_LOSS_NOT_AVAILABLE")
    return targets, notes


def macros_for(
    energy: float,
    profile: JSON,
    weight_kg: float,
    now: float,
    policy: JSON,
    basis: str,
    notes: list[str],
    floor: float = 0.0,
) -> JSON:
    """Split ``energy`` into protein, fat and carbohydrate targets under the policy's bounds.

    Energy is shown to the nearest 10 kcal, rounded up when that would fall below ``floor``.
    """
    per_gram = parameter(policy, "energy.kcalPerGram")
    protein = protein_target(profile, weight_kg, policy)
    # Protein never exceeds the top of its acceptable share of energy (IOM AMDR).
    protein = min(protein, parameter(policy, "macros.proteinMaximumEnergyFraction") * energy / per_gram["protein"])
    fat_minimum = parameter(policy, "macros.fatMinimumEnergyFraction") * energy / per_gram["fat"]
    fat_maximum = parameter(policy, "macros.fatMaximumEnergyFraction") * energy / per_gram["fat"]
    carbohydrate_floor = parameter(policy, "macros.carbohydrateMinimumGPerDay")
    if profile["goal"] == "endurance" and profile.get("trainingLoad"):
        low, high = parameter(policy, "goals.endurance.carbohydrateGPerKgByTrainingLoad")[profile["trainingLoad"]]
        carbohydrate = max(carbohydrate_floor, (low + high) / 2 * weight_kg)
        fat = (energy - protein * per_gram["protein"] - carbohydrate * per_gram["carbohydrate"]) / per_gram["fat"]
        if fat < fat_minimum:
            # Fuelling the training load comes first; energy rises until fat reaches its
            # minimum share of the new, higher energy: E = (4P + 4C) / (1 - fat share).
            fat_share = parameter(policy, "macros.fatMinimumEnergyFraction")
            energy = (protein * per_gram["protein"] + carbohydrate * per_gram["carbohydrate"]) / (1 - fat_share)
            fat = fat_share * energy / per_gram["fat"]
            fat_maximum = parameter(policy, "macros.fatMaximumEnergyFraction") * energy / per_gram["fat"]
            notes.append("ENERGY_RAISED_FOR_CARBOHYDRATE")
        if fat > fat_maximum:
            # Energy above the fat ceiling goes to carbohydrate, so the targets still add up.
            carbohydrate += (fat - fat_maximum) * per_gram["fat"] / per_gram["carbohydrate"]
            fat = fat_maximum
    else:
        fat = parameter(policy, "macros.fatDefaultEnergyFraction") * energy / per_gram["fat"]
        carbohydrate = (energy - protein * per_gram["protein"] - fat * per_gram["fat"]) / per_gram["carbohydrate"]
        if carbohydrate < carbohydrate_floor:
            fat = max(
                fat_minimum,
                (energy - protein * per_gram["protein"] - carbohydrate_floor * per_gram["carbohydrate"])
                / per_gram["fat"],
            )
            carbohydrate = (energy - protein * per_gram["protein"] - fat * per_gram["fat"]) / per_gram["carbohydrate"]
        if carbohydrate < carbohydrate_floor:
            carbohydrate = carbohydrate_floor
            energy = protein * per_gram["protein"] + carbohydrate * per_gram["carbohydrate"] + fat * per_gram["fat"]
            notes.append("ENERGY_RAISED_FOR_CARBOHYDRATE_FLOOR")
    fibre = parameter(policy, "macros.fibreGPer1000Kcal") * energy / 1000
    fibre = min(max(fibre, parameter(policy, "macros.fibreMinimumG")), parameter(policy, "macros.fibreMaximumG"))
    shown_energy = round(energy / 10) * 10
    if shown_energy < floor:
        shown_energy = math.ceil(floor / 10) * 10
    return {
        "energyKcal": shown_energy,
        "proteinG": round(protein),
        "carbohydrateG": round(carbohydrate),
        "fatG": round(fat),
        "fibreG": round(fibre),
        "policyVersion": policy["version"],
        "basis": basis,
        "setAt": now,
    }


def protein_target(profile: JSON, weight_kg: float, policy: JSON) -> float:
    """Daily protein (g) for the goal, on the policy's body mass for high BMI, within its bounds."""
    mass = protein_body_mass(weight_kg, profile["heightCm"], policy)
    per_kg = parameter(policy, f"goals.{profile['goal']}.proteinGPerKgBodyMass")
    per_kg *= (
        parameter(policy, f"patterns.{profile['pattern']}.proteinMultiplier")
        if profile["pattern"] != "omnivore"
        else 1.0
    )
    per_kg = min(
        max(per_kg, parameter(policy, "macros.proteinMinimumGPerKgBodyMass")),
        parameter(policy, "macros.proteinMaximumGPerKgBodyMass"),
    )
    return float(per_kg * mass)


def protein_body_mass(weight_kg: float, height_cm: float, policy: JSON) -> float:
    """Body mass for g/kg protein targets: actual mass, or the reference mass once BMI reaches the policy's cut-off."""
    height_m = height_cm / 100
    if weight_kg / (height_m * height_m) >= parameter(policy, "macros.proteinReferenceFromBMI"):
        return float(parameter(policy, "macros.proteinReferenceBMI") * height_m * height_m)
    return weight_kg


# --- weight trend and adjustment ----------------------------------------------------------


def daily_weigh_ins(weigh_ins: Sequence[JSON]) -> list[JSON]:
    """The first weigh-in of each local day, oldest first (repeat readings on one day add no evidence)."""
    first_by_day: dict[int, JSON] = {}
    for weigh_in in sorted(weigh_ins, key=lambda w: w["measuredAt"]):
        day = int((weigh_in["measuredAt"] + weigh_in["utcOffsetSeconds"]) // DAY)
        first_by_day.setdefault(day, weigh_in)
    return [first_by_day[day] for day in sorted(first_by_day)]


def current_weight(weigh_ins: Sequence[JSON], now: float, policy: JSON, pace: str | None = None) -> float | None:
    """The trend weight when a trend exists, else the latest weigh-in (kg), else None."""
    trend = weight_trend(list(weigh_ins), now, policy, pace=pace)
    if trend is not None:
        return float(trend["latestKg"])
    daily = [w for w in daily_weigh_ins(weigh_ins) if w["measuredAt"] <= now]
    return float(daily[-1]["kg"]) if daily else None


def weight_trend(
    weigh_ins: list[JSON], now: float, policy: JSON, since: float | None = None, pace: str | None = None
) -> JSON | None:
    """The least-squares trend of one weigh-in per day in the policy window (from ``since`` if later).

    None unless there are at least ``minimumWeighIns`` days and every 7-day block of the window
    holds ``minimumWeighInDaysPerWeek`` of them: an uneven spread biases the slope.
    """
    pace = pace or parameter(policy, "adaptation.defaultPace")
    window_days = pace_parameter(policy, pace, "windowDays")
    start = now - window_days * DAY if since is None else max(now - window_days * DAY, since)
    recent = [w for w in daily_weigh_ins(weigh_ins) if start <= w["measuredAt"] <= now]
    if len(recent) < pace_parameter(policy, pace, "minimumWeighIns"):
        return None
    per_week = pace_parameter(policy, pace, "minimumWeighInDaysPerWeek")
    block_end = now
    while block_end - WEEK_DAYS * DAY >= start:  # full 7-day blocks back from now; a shorter remainder is not judged
        block_start = block_end - WEEK_DAYS * DAY
        in_block = [
            w
            for w in recent
            if block_start <= w["measuredAt"] < block_end or (block_end == now and w["measuredAt"] == now)
        ]
        if len(in_block) < per_week:
            return None
        block_end = block_start
    times = [w["measuredAt"] / DAY for w in recent]
    masses = [w["kg"] for w in recent]
    mean_time = sum(times) / len(times)
    mean_mass = sum(masses) / len(masses)
    spread = sum((t - mean_time) ** 2 for t in times)
    if spread == 0:
        return None  # all on one instant: no rate can be read
    slope_per_day = sum((t - mean_time) * (m - mean_mass) for t, m in zip(times, masses, strict=True)) / spread
    # Fitted at the latest weigh-in, not at ``now``, so a preview and its acceptance a moment
    # later compute the same weight.
    fitted_latest = mean_mass + slope_per_day * (times[-1] - mean_time)
    weekly_kg = slope_per_day * WEEK_DAYS
    return {
        "latestKg": round(fitted_latest, 2),
        "weeklyChangeKg": round(weekly_kg, 3),
        "weeklyChangeFraction": round(weekly_kg / fitted_latest, 5),
        "weighIns": len(recent),
        "windowDays": math.ceil((now - start) / DAY),  # the days actually covered
    }


def adjustment_for(state: JSON, now: float, policy: JSON) -> JSON | None:
    """One suggested change to the accepted targets, or None when the trend is on course or unknown."""
    profile, targets = state.get("dietProfile"), state.get("dietTargets")
    if profile is None or targets is None or safety_block(profile, now, policy, state["weighIns"]) is not None:
        return None
    last_decision = max([targets["setAt"]] + [d["decidedAt"] for d in state["dietDecisions"]])
    pace = pace_of(profile, policy)
    # Only weigh-ins taken under the current target count toward changing it.
    trend = weight_trend(state["weighIns"], now, policy, since=last_decision, pace=pace)
    if trend is None:
        return None
    direction, reason = _direction(profile["goal"], trend["weeklyChangeFraction"], policy, pace)
    if direction == 0:
        return None
    too_soon = now - last_decision < pace_parameter(policy, pace, "minimumDaysBetweenAdjustments") * DAY
    if too_soon and reason != "LOSING_FASTER_THAN_SAFE":
        return None  # the loss ceiling is a safety check and does not wait out the interval
    step = pace_parameter(policy, pace, "adjustmentStepKcal") * direction
    weight = trend["latestKg"]
    requirement = estimated_energy_requirement(profile, weight, now, policy)
    floor = energy_floor(profile, weight, requirement, policy)
    proposed = macros_for(
        max(targets["energyKcal"] + step, floor), profile, weight, now, policy, "adjustment", [], floor=floor
    )
    change = proposed["energyKcal"] - targets["energyKcal"]
    # Judge the final, rounded proposal: a floor, rounding or endurance carbohydrate can cancel
    # or even reverse the step, and a no-op or reversed suggestion is never shown.
    if change == 0 or (change > 0) != (direction > 0):
        return None
    unit = (state.get("profile") or {}).get("preferredUnit", "kg")
    return {"targets": proposed, "reason": reason, **_adjustment_copy(reason, trend, proposed, targets, unit)}


def _direction(goal: str, observed: float, policy: JSON, pace: str) -> tuple[int, str]:
    """+1 to eat more, -1 to eat less, 0 to keep, and the reason code."""
    tolerance = pace_parameter(policy, pace, "toleranceFractionPerWeek")
    if goal == "fatLoss":
        target = parameter(policy, "goals.fatLoss.weeklyChangeFraction")
        if observed < -parameter(policy, "goals.fatLoss.maxWeeklyLossFraction"):
            return 1, "LOSING_FASTER_THAN_SAFE"
        if observed > target + tolerance:
            return -1, "LOSING_SLOWER_THAN_GOAL"
        return 0, "ON_COURSE"
    if goal == "muscleGain":
        target = parameter(policy, "goals.muscleGain.weeklyChangeFraction")
        if observed > parameter(policy, "goals.muscleGain.maxWeeklyGainFraction"):
            return -1, "GAINING_FASTER_THAN_GOAL"
        if observed < target - tolerance:
            return 1, "GAINING_SLOWER_THAN_GOAL"
        return 0, "ON_COURSE"
    band = parameter(policy, "goals.maintenance.stableBandFractionPerWeek")
    if observed > band:
        return -1, "WEIGHT_RISING"
    if observed < -band:
        return 1, "WEIGHT_FALLING"
    return 0, "ON_COURSE"


def _adjustment_copy(reason: str, trend: JSON, proposed: JSON, current: JSON, unit: str) -> JSON:
    change = proposed["energyKcal"] - current["energyKcal"]
    verb = "Raise" if change > 0 else "Lower"
    weekly = trend["weeklyChangeKg"]
    amount = abs(weekly) / KILOGRAMS_PER_POUND if unit == "lb" else abs(weekly)
    moving = f"{'gaining' if weekly > 0 else 'losing'} {amount:.2f} {unit} a week"
    if proposed["proteinG"] == current["proteinG"]:
        protein = f"protein stays at {proposed['proteinG']} g"
    else:
        protein = f"protein moves from {current['proteinG']} g to {proposed['proteinG']} g with your weight"
    reasons = {
        "LOSING_FASTER_THAN_SAFE": "faster than the safe rate for your goal",
        "LOSING_SLOWER_THAN_GOAL": "slower than your fat-loss goal",
        "GAINING_FASTER_THAN_GOAL": "faster than a lean-gain rate",
        "GAINING_SLOWER_THAN_GOAL": "slower than your muscle-gain goal",
        "WEIGHT_RISING": "more than a stable weight allows",
        "WEIGHT_FALLING": "more than a stable weight allows",
    }
    return {
        "title": f"{verb} daily energy to {proposed['energyKcal']} kcal",
        "body": (
            f"Over the last {trend['windowDays']} days ({trend['weighIns']} weigh-ins) you are {moving}, "
            f"{reasons[reason]}. {verb} by {abs(change)} kcal; {protein}."
        ),
    }
