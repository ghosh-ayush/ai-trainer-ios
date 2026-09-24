"""Foods from USDA FoodData Central (public domain, CC0): search, portions and suggestions.

The table (``data/foods.json``) is built by ``scripts/build_food_data.py``. Composition
values are USDA's, per 100 g; the app never estimates a nutrient. Suggestions only rank
foods the table marks ``suggestable`` for the athlete's dietary pattern, and never offer a
portion bigger than what is left of today's energy.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .errors import DomainError, require

JSON = dict[str, Any]

TABLE_PATH = Path(__file__).with_name("data") / "foods.json"
DEFAULT_PORTION = ("100 g", 100.0)
MAXIMUM_RESULTS = 50


@lru_cache(maxsize=1)
def table() -> list[JSON]:
    """Every food, as dicts. Read once per process."""
    raw = json.loads(TABLE_PATH.read_text())
    fields = raw["fields"]
    return [dict(zip(fields, row, strict=True)) for row in raw["foods"]]


@lru_cache(maxsize=1)
def _by_id() -> dict[int, JSON]:
    return {food["id"]: food for food in table()}


def food(food_id: int) -> JSON:
    """One food by FDC id; ``notFound`` when the table has no such food."""
    found = _by_id().get(food_id)
    if found is None:
        raise DomainError("notFound", "That food is not in the bundled table.")
    return found


def search(query: str, pattern: str | None, limit: int) -> list[JSON]:
    """Foods whose name contains every word of ``query``, best matches first, as ``FoodItem``s."""
    words = [word for word in query.lower().split() if word]
    if not words:
        return []
    limit = max(1, min(limit, MAXIMUM_RESULTS))
    matches = [
        candidate
        for candidate in table()
        if all(word in candidate["name"].lower() for word in words)
        and (pattern is None or pattern in candidate["patterns"])
    ]
    first = words[0]
    matches.sort(key=lambda c: (not c["name"].lower().startswith(first), c["dataset"] != "fndds", len(c["name"])))
    return [food_item(candidate) for candidate in matches[:limit]]


def food_item(candidate: JSON) -> JSON:
    """The contract ``FoodItem`` for one table row."""
    item: JSON = {
        "id": candidate["id"],
        "name": candidate["name"],
        "category": candidate["category"],
        "per100g": nutrients_per(candidate, 100.0),
        "portions": portions(candidate),
        "patterns": candidate["patterns"],
    }
    if candidate["fibre"] is not None:
        item["fibre"] = candidate["fibre"]
    return item


def portions(candidate: JSON) -> list[JSON]:
    """The food's household portions, or 100 g when USDA lists none."""
    listed = [{"label": label, "grams": grams} for label, grams in candidate["portions"]]
    return listed or [{"label": DEFAULT_PORTION[0], "grams": DEFAULT_PORTION[1]}]


def nutrients_per(candidate: JSON, grams: float) -> JSON:
    """The contract ``Nutrients`` in ``grams`` of a food, from its per-100 g composition."""
    require(grams > 0, "invalid", "Grams must be greater than zero.")
    factor = grams / 100.0
    return {
        "calories": round(candidate["kcal"] * factor, 1),
        "protein": round(candidate["protein"] * factor, 1),
        "carbs": round(candidate["carbohydrate"] * factor, 1),
        "fat": round(candidate["fat"] * factor, 1),
    }


def suggest(remaining: JSON, targets: JSON, profile: JSON, policy: JSON, limit: int = 6) -> list[JSON]:
    """Foods that fit what is left of today, ranked for the nutrient that is furthest behind.

    Ranking (diet-1 ``foods``): when protein is further behind than energy, prefer
    protein-dense foods (the Codex "high in protein" criteria restated by FAO 2013, both per
    100 kcal and per 100 g);
    otherwise prefer fibre per kcal. A suggested portion must deliver at least the policy's
    protein or fibre, so an idea is worth eating. Only as-eaten FNDDS dishes are suggested.
    Foods tagged with a cuisine the athlete chose rank first within each tier. At most two
    foods per category and no repeated names, so the list stays varied.
    """
    energy_left = remaining["calories"]
    if energy_left <= 0:
        return []
    protein_share = max(remaining["protein"], 0) / targets["proteinG"] if targets["proteinG"] else 0.0
    energy_share = energy_left / targets["energyKcal"] if targets["energyKcal"] else 0.0
    if profile["goal"] in ("muscleGain", "endurance"):
        # diet-1 (macros.fibreMaximumG rationale): no fibre bonus for a surplus or for energy
        # availability, so these goals keep protein-first ideas until protein is met.
        protein_first = remaining["protein"] > 0
    else:
        protein_first = protein_share >= energy_share  # a tie (nothing eaten yet) favours protein
    protein_dense = policy["foods"]["proteinDenseGPer100Kcal"]
    protein_dense_per_100g = policy["foods"]["proteinDenseMinGPer100g"]
    minimum_protein = policy["foods"]["minimumPortionProteinG"]
    minimum_fibre = policy["foods"]["minimumPortionFibreG"]
    cuisines = set(profile.get("cuisines") or [])
    candidates = []
    for candidate in table():
        # Only as-eaten survey foods (FNDDS): real dishes with household portions, not ingredients.
        if (
            candidate["dataset"] != "fndds"
            or not candidate["suggestable"]
            or profile["pattern"] not in candidate["patterns"]
        ):
            continue
        label, grams = _first_portion(candidate)
        portion_kcal = candidate["kcal"] * grams / 100
        if portion_kcal <= 0 or portion_kcal > energy_left:
            continue
        portion_protein = candidate["protein"] * grams / 100
        portion_fibre = (candidate["fibre"] or 0) * grams / 100
        protein_per_100kcal = candidate["protein"] * 100 / candidate["kcal"] if candidate["kcal"] else 0
        fibre_per_100kcal = (candidate["fibre"] or 0) * 100 / candidate["kcal"] if candidate["kcal"] else 0
        if protein_first:
            if (
                protein_per_100kcal < protein_dense
                or candidate["protein"] < protein_dense_per_100g
                or portion_protein < minimum_protein
            ):
                continue
            score = protein_per_100kcal
        else:
            if portion_fibre < minimum_fibre:
                continue
            score = fibre_per_100kcal
        preferred = bool(cuisines & set(candidate["cuisines"]))
        candidates.append((not preferred, -score, len(candidate["name"]), candidate, label, grams))
    candidates.sort(key=lambda entry: entry[:3])
    chosen: list[JSON] = []
    per_category: dict[str, int] = {}
    seen_names: set[str] = set()
    for _, _, _, candidate, label, grams in candidates:
        if per_category.get(candidate["category"], 0) >= 2 or candidate["name"].lower() in seen_names:
            continue
        seen_names.add(candidate["name"].lower())
        per_category[candidate["category"]] = per_category.get(candidate["category"], 0) + 1
        nutrients = nutrients_per(candidate, grams)
        focus = (
            f"{nutrients['protein']:g} g protein"
            if protein_first
            else f"{(candidate['fibre'] or 0) * grams / 100:.1f} g fibre"
        )
        chosen.append(
            {
                "foodID": candidate["id"],
                "name": candidate["name"],
                "portion": {"label": label, "grams": grams},
                "nutrients": nutrients,
                "reason": f"{focus} for {nutrients['calories']:g} kcal in {label}",
            }
        )
        if len(chosen) == limit:
            break
    return chosen


def _first_portion(candidate: JSON) -> tuple[str, float]:
    listed = candidate["portions"]
    return (listed[0][0], listed[0][1]) if listed else DEFAULT_PORTION
