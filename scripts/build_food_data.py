#!/usr/bin/env python3
"""Build the bundled food table from USDA FoodData Central downloads (CC0 1.0, public domain).

Usage: python3 scripts/build_food_data.py <directory holding the three unzipped FDC downloads>

Inputs (download from https://fdc.nal.usda.gov/download-datasets/, unzip in one directory):
  FoodData_Central_foundation_food_json_2025-12-18/   Foundation Foods (JSON)
  FoodData_Central_sr_legacy_food_csv_2018-04/        SR Legacy (CSV)
  FoodData_Central_survey_food_json_2024-10-31/       FNDDS survey foods (JSON)
Output: core/python/ai_trainer/data/foods.json

For each food the table keeps what the diet engine uses and nothing else: energy (kcal),
protein, carbohydrate, fat and fibre per 100 g, up to three household portions, the FDC
category, which dietary patterns the food fits, and reviewed cuisine tags.

Pattern tags are derived, never guessed. FNDDS foods: every ingredient, expanding nested
FNDDS recipes down to SR Legacy codes, is classed by its USDA food group as meat, animal
(dairy or egg), plant, or uncertain (a group that can hide gelatin, lard, broth or dairy),
and its description is checked for animal words. SR Legacy and Foundation foods: their FDC
category and name. A food is tagged ``vegan`` only when every part is plant, and
``vegetarian`` only when no part is meat or uncertain. Anything uncertain loses the tag
(safe direction). Cuisine tags are the reviewed (food, cuisine) pairs in
docs/research/cuisine-tags.json (candidates from dish-name keywords and Wikidata, CC0) — a
ranking aid for suggestions, never a nutrition value.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "core/python/ai_trainer/data/foods.json"

FOUNDATION = "FoodData_Central_foundation_food_json_2025-12-18"
SR_LEGACY = "FoodData_Central_sr_legacy_food_csv_2018-04"
SURVEY = "FoodData_Central_survey_food_json_2024-10-31"

# FDC nutrient ids.
ENERGY_KCAL = 1008
ENERGY_ATWATER_GENERAL = 2047
ENERGY_ATWATER_SPECIFIC = 2048
PROTEIN = 1003
FAT = 1004
CARBOHYDRATE = 1005
FIBRE = 1079

# SR Legacy / Foundation categories whose foods are animal flesh, or animal-derived.
MEAT_CATEGORIES = {
    "Poultry Products",
    "Sausages and Luncheon Meats",
    "Pork Products",
    "Beef Products",
    "Finfish and Shellfish Products",
    "Lamb, Veal, and Game Products",
}
ANIMAL_CATEGORIES = MEAT_CATEGORIES | {"Dairy and Egg Products"}
# SR Legacy / Foundation categories whose foods are plants: the only ones that can be vegan,
# because these datasets list no ingredients (a cookie or cereal may hide butter or honey).
PLANT_CATEGORIES = {
    "Vegetables and Vegetable Products",
    "Fruits and Fruit Juices",
    "Legumes and Legume Products",
    "Cereal Grains and Pasta",
    "Nut and Seed Products",
    "Spices and Herbs",
    "Fats and Oils",
}
# Categories that mix foods of unknown composition: never tagged vegetarian or vegan.
MIXED_CATEGORIES = {
    "Fast Foods",
    "Meals, Entrees, and Side Dishes",
    "Restaurant Foods",
    "Baby Foods",
    "American Indian/Alaska Native Foods",
}

# USDA SR NDB food groups (code // 1000 for 4-5 digit codes) by what they can contain.
SR_MEAT_GROUPS = {5, 7, 10, 13, 15, 17}
SR_ANIMAL_GROUPS = {1}  # dairy and egg
SR_PLANT_GROUPS = {2, 9, 11, 12, 16, 20}  # spices, fruits, vegetables, nuts/seeds, legumes, grains
SR_VEGETARIAN_GROUPS = {
    8,
    14,
    18,
    25,
    28,
}  # cereals, beverages, baked goods (18, 28), snacks: may hold dairy or egg, not meat
# Every other group (baby foods, fats and oils, soups and sauces, sweets, fast foods, meals,
# restaurant, special) is uncertain: it can hide lard, broth, gelatin or anchovy.
FNDDS_MEAT_GROUP = 2
FNDDS_ANIMAL_GROUPS = {1, 3}
FNDDS_PLANT_GROUPS = {4, 6, 7}

MEAT_WORDS = re.compile(
    r"\b(beef|pork|ham|bacon|chicken|turkey|duck|goose|lamb|veal|venison|bison|goat|meats?|"
    r"sausages?|salami|pepperoni|bologna|frankfurters?|franks?|hot dogs?|fish|salmon|tuna|cod|"
    r"tilapia|shrimp|crabs?|lobster|clams?|oysters?|mussels?|scallops?|squid|octopus|anchov\w*|"
    r"sardines?|herring|mackerel|trout|catfish|seafood|lard|tallow|gelatins?|broth|au jus|"
    r"worcestershire|caesar|fish sauce|jerky|pâté|pate|liver)\b",
    re.I,
)
ANIMAL_WORDS = re.compile(
    r"\b(milk|cheese\w*|butter|ghee|cream\w*|yogurt|yoghurt|whey|casein|eggs?|egg noodles?|honey|"
    r"mayonnaise|custard|pudding|souffl\w*|au gratin|scalloped|ranch|alfredo|paneer|kefir|"
    r"buttermilk|meringue|french toast|pancakes?|waffles?|fresh-refrigerated|potato salad)\b",
    re.I,
)
PLANT_EXCEPTIONS = re.compile(
    r"\b(peanut butter|almond butter|nut butter|cocoa butter|apple butter|soymilk|soy milk|"
    r"almond milk|oat milk|rice milk|coconut milk|coconut cream|plant-based|meatless|"
    r"vegan|egg replacer|butternut|cream of tartar|eggplant|buttermilk substitute)\b",
    re.I,
)

# Cuisine tags come only from the reviewed list (docs/research/cuisine-tags.json), built by
# scripts/cuisine_candidates.py plus a two-reviewer check.
CUISINE_TAGS = ROOT / "docs/research/cuisine-tags.json"

# Categories kept for logging but never suggested: infant foods, alcohol, sweets and
# similar (the ultra-processed-food evidence supports not promoting them; see diet-1).
NOT_SUGGESTED = re.compile(
    r"\b(baby|formula|human milk|liquor|beer|wine|cocktails?|candy|soft drinks?|diet drinks?|sugars?|"
    r"honey|syrups?|jams?|toppings?|cookies|brownies?|cakes?|pies?|doughnuts?|pastr\w*|ice cream|"
    r"frozen dairy|gelatins?|sorbets?|condiments?|mustard|mayonnaise|salad dressings?|water|"
    r"bottled water|tap water|coffee|tea|energy drinks?|sport and energy|fruit drinks?|margarine|"
    r"butter and animal fats|chips|pretzels?|popcorn|snacks?|snack mix|"
    # Sauces, fats and supplements are logged, not suggested as food ideas.
    r"sauces?|gravy|gravies|dips|olives|pickles|vegetable oils|cream and cream substitutes|"
    r"cream cheese|protein and nutritional powders|nutritional beverages|nutrition bars|"
    r"not included in a food category|isolate|flour|powder)\b",
    re.I,
)


# Branded and restaurant items (an all-capitals brand word) stay searchable for logging but are
# not suggested: a suggestion should be a food anyone can buy or cook.
BRAND_NAME = re.compile(r"\b(?!(?:NFS|NS|USDA|RTE|UPC)\b)[A-Z][A-Z'&]{2,}\b")  # NFS = "not further specified"
# Raw animal foods and raw-fish dishes are logged but never suggested; raw plants are fine.
RAW = re.compile(r"\b(raw|ceviche|sushi|sashimi|tartare|poke|crudo)\b", re.I)


def main() -> None:
    """Read the three downloads and write the compact food table."""
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_food_data.py <directory with the unzipped FDC downloads>")
    base = Path(sys.argv[1])
    global _CUISINES_BY_FOOD
    _CUISINES_BY_FOOD = {}
    for tag in json.loads(CUISINE_TAGS.read_text())["tags"]:
        _CUISINES_BY_FOOD.setdefault(tag["foodID"], []).append(tag["cuisine"])
    foods: list[dict] = []
    foods += _foundation(base / FOUNDATION / f"{FOUNDATION}.json")
    foods += _sr_legacy(base / SR_LEGACY / SR_LEGACY)
    foods += _survey(base / SURVEY / "surveyDownload.json")
    foods = [food for food in foods if food is not None]
    foods.sort(key=lambda food: (food["name"].lower(), food["id"]))
    table = {
        "source": "USDA FoodData Central (https://fdc.nal.usda.gov). Public domain, CC0 1.0. Cuisine tags: "
        "docs/research/cuisine-tags.json (Wikidata CC0 and keywords, two-reviewer checked).",
        "datasets": {name: _sha256(base / f"{name}.zip") for name in (FOUNDATION, SR_LEGACY, SURVEY)},
        "units": "per 100 g: kcal, protein g, carbohydrate g, fat g, fibre g; portions in grams",
        "fields": [
            "id",
            "name",
            "dataset",
            "category",
            "kcal",
            "protein",
            "carbohydrate",
            "fat",
            "fibre",
            "patterns",
            "cuisines",
            "suggestable",
            "portions",
        ],
        "foods": [
            [
                food[field]
                for field in (
                    "id",
                    "name",
                    "dataset",
                    "category",
                    "kcal",
                    "protein",
                    "carbohydrate",
                    "fat",
                    "fibre",
                    "patterns",
                    "cuisines",
                    "suggestable",
                    "portions",
                )
            ]
            for food in foods
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(table, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Wrote {len(foods)} foods to {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size // 1024} KB)")


def _foundation(path: Path) -> list[dict | None]:
    records = json.loads(path.read_text())["FoundationFoods"]
    return [
        _food(
            record["fdcId"],
            record["description"],
            "foundation",
            (record.get("foodCategory") or {}).get("description", ""),
            {entry["nutrient"]["id"]: entry.get("amount") for entry in record["foodNutrients"]},
            [(_portion_label(p), p.get("gramWeight")) for p in record.get("foodPortions", [])],
            _category_patterns((record.get("foodCategory") or {}).get("description", ""), record["description"]),
        )
        for record in records
    ]


def _sr_legacy(directory: Path) -> list[dict | None]:
    categories = {row["id"]: row["description"] for row in _rows(directory / "food_category.csv")}
    nutrients: dict[str, dict[int, float]] = {}
    wanted = {ENERGY_KCAL, PROTEIN, FAT, CARBOHYDRATE, FIBRE}
    for row in _rows(directory / "food_nutrient.csv"):
        nutrient_id = int(row["nutrient_id"])
        if nutrient_id in wanted:
            nutrients.setdefault(row["fdc_id"], {})[nutrient_id] = float(row["amount"])
    units = {row["id"]: row["name"] for row in _rows(directory / "measure_unit.csv")}
    portions: dict[str, list[tuple[str, float]]] = {}
    for row in _rows(directory / "food_portion.csv"):
        label = " ".join(
            part
            for part in (
                row.get("amount", ""),
                row.get("modifier", "") or units.get(row.get("measure_unit_id", ""), ""),
            )
            if part
        )
        portions.setdefault(row["fdc_id"], []).append((label.strip(), float(row["gram_weight"] or 0)))
    foods = []
    for row in _rows(directory / "food.csv"):
        category = categories.get(row["food_category_id"], "")
        foods.append(
            _food(
                int(row["fdc_id"]),
                row["description"],
                "srLegacy",
                category,
                nutrients.get(row["fdc_id"], {}),
                portions.get(row["fdc_id"], []),
                _category_patterns(category, row["description"]),
            )
        )
    return foods


def _survey(path: Path) -> list[dict | None]:
    records = json.loads(path.read_text())["SurveyFoods"]
    global _SURVEY_BY_CODE
    _SURVEY_BY_CODE = {int(record.get("foodCode") or 0): record for record in records}
    foods = []
    for record in records:
        category = (record.get("wweiaFoodCategory") or {}).get("wweiaFoodCategoryDescription", "")
        foods.append(
            _food(
                record["fdcId"],
                record["description"],
                "fndds",
                category,
                {entry["nutrient"]["id"]: entry.get("amount") for entry in record["foodNutrients"]},
                [(p.get("portionDescription", ""), p.get("gramWeight")) for p in record.get("foodPortions", [])],
                _survey_patterns(record),
            )
        )
    return foods


def _food(fdc_id, name, dataset, category, nutrients, portions, patterns) -> dict | None:
    kcal = nutrients.get(ENERGY_KCAL)
    if kcal is None:
        kcal = nutrients.get(ENERGY_ATWATER_SPECIFIC, nutrients.get(ENERGY_ATWATER_GENERAL))
    macros = [nutrients.get(PROTEIN), nutrients.get(CARBOHYDRATE), nutrients.get(FAT)]
    if kcal is None or any(value is None for value in macros):
        return None  # incomplete composition: never shown, never estimated
    kept_portions = [
        [label, round(float(grams), 1)]
        for label, grams in portions
        if label and grams and float(grams) > 0 and "not specified" not in label.lower()
    ][:3]
    # Carbohydrate "by difference" can come out slightly negative in USDA data; no food holds
    # less than none, so every value is floored at zero.
    macros = [max(0.0, float(value)) for value in macros]
    return {
        "id": int(fdc_id),
        "name": name.strip(),
        "dataset": dataset,
        "category": category,
        "kcal": round(max(0.0, float(kcal)), 1),
        "protein": round(macros[0], 2),
        "carbohydrate": round(macros[1], 2),
        "fat": round(macros[2], 2),
        "fibre": None if nutrients.get(FIBRE) is None else round(max(0.0, float(nutrients[FIBRE])), 2),
        "patterns": patterns,
        "cuisines": sorted(set(_CUISINES_BY_FOOD.get(int(fdc_id), []))),
        "suggestable": (
            not NOT_SUGGESTED.search(f"{category} {name}")
            and not BRAND_NAME.search(name)
            # Raw meat, fish and eggs are logged but never suggested; raw plants are fine.
            and not (RAW.search(name) and "vegan" not in patterns)
        ),
        "portions": kept_portions,
    }


def _category_patterns(category: str, name: str) -> list[str]:
    """Dietary patterns an SR Legacy / Foundation food fits, from its category and name."""
    patterns = ["omnivore"]
    if category in MEAT_CATEGORIES or category in MIXED_CATEGORIES or MEAT_WORDS.search(name):
        return patterns
    patterns.append("vegetarian")
    animal = category in ANIMAL_CATEGORIES or (ANIMAL_WORDS.search(name) and not PLANT_EXCEPTIONS.search(name))
    if category in PLANT_CATEGORIES and not animal:
        patterns.append("vegan")
    return patterns


_SURVEY_BY_CODE: dict[int, dict] = {}
MEAT, UNCERTAIN, ANIMAL, VEGETARIAN_ONLY, PLANT = "meat", "uncertain", "animal", "vegetarianOnly", "plant"


def _survey_patterns(record: dict) -> list[str]:
    """Dietary patterns an FNDDS food fits, from its own code and every (nested) ingredient."""
    if not record.get("inputFoods"):
        return ["omnivore"]  # no ingredient list to check
    classes = _classes(record, depth=0)
    return _patterns_from(classes)


def _classes(record: dict, depth: int) -> set[str]:
    """What an FNDDS food can contain: its description and each ingredient (its own code only when it lists none).

    A dish's own food-group code is coarse (every grain dish is "uncertain"), so once its
    ingredients are known they decide; the code can still mark a dish as meat.
    """
    own = _fndds_code_class(int(record.get("foodCode") or 0))
    if TABLE_FAT.search(record["description"]):
        return {VEGETARIAN_ONLY}
    if not record.get("inputFoods"):
        return {own, _text_class(record["description"])}
    found = {_text_class(record["description"])} | ({MEAT} if own == MEAT else set())
    for ingredient in record.get("inputFoods", []):
        code = int(ingredient.get("ingredientCode") or 0)
        found.add(_text_class(ingredient.get("ingredientDescription", "")))
        nested = _SURVEY_BY_CODE.get(code)
        if nested is not None and nested is not record and depth < 6:
            found |= _classes(nested, depth + 1)  # a recipe used as an ingredient
        elif 10_000_000 <= code <= 99_999_999:
            found.add(_fndds_code_class(code))
        else:
            found.add(_sr_code_class(code, ingredient.get("ingredientDescription", "")))
    return found


def _patterns_from(classes: set[str]) -> list[str]:
    if MEAT in classes or UNCERTAIN in classes:
        return ["omnivore"]
    if ANIMAL in classes or VEGETARIAN_ONLY in classes:
        return ["omnivore", "vegetarian"]
    return ["omnivore", "vegetarian", "vegan"]


def _fndds_code_class(code: int) -> str:
    group = code // 10_000_000
    if group == FNDDS_MEAT_GROUP:
        return MEAT
    if group in FNDDS_ANIMAL_GROUPS:
        return ANIMAL
    if group in FNDDS_PLANT_GROUPS:
        return PLANT
    return UNCERTAIN  # grains, fats, sweets and beverages can hold egg, dairy, lard or gelatin


# Within otherwise uncertain SR groups, names that are plainly plant-derived.
PLANT_OIL = re.compile(
    r"^(oil|vegetable oil|shortening, vegetable|margarine-like|salad or cooking oil)"
    r"|\boil, (canola|olive|soybean|corn|peanut|sunflower|safflower|sesame|coconut|palm|vegetable)",
    re.I,
)
PLANT_SWEETENER = re.compile(r"^(sugars?|syrups?, (maple|corn|cane)|molasses|cocoa|sweeteners?|baking chocolate)", re.I)
PLANT_BEVERAGE = re.compile(r"\b(water|coffee|tea|juice)\b", re.I)
LEAVENING = re.compile(r"^leavening agents", re.I)
PLAIN_CEREAL = re.compile(
    r"^cereals, (oats|oat bran|wheat bran|farina|corn grits|whole wheat hot|cream of (wheat|rice))", re.I
)
STOCK = re.compile(r"\b(soup|gravy|broth|bouillon|stock)\b", re.I)
# Unspecified cooking fat is plant oil or butter/margarine: vegetarian, not vegan (owner, 2026-09-24).
TABLE_FAT = re.compile(r"^(oil or table fat|table fat|margarine)", re.I)


def _sr_code_class(code: int, name: str = "") -> str:
    if code >= 100_000:
        # Newer FDC ids carry no food-group prefix: only the name can clear them.
        text = _text_class(name)
        return text if text != PLANT else (PLANT if PLANT_OIL.search(name) else UNCERTAIN)
    if not 1_000 <= code < 100_000:
        return UNCERTAIN
    group = code // 1_000
    if group in SR_MEAT_GROUPS:
        return MEAT
    if group in SR_ANIMAL_GROUPS:
        return ANIMAL
    if group in SR_PLANT_GROUPS:
        return PLANT
    text = _text_class(name)
    if text != PLANT:
        return text  # a named animal or meat ingredient decides it
    if group == 4 and PLANT_OIL.search(name):
        return PLANT
    if group == 4 and TABLE_FAT.search(name):
        return VEGETARIAN_ONLY
    if group == 19 and PLANT_SWEETENER.search(name):
        return PLANT
    if group == 14 and PLANT_BEVERAGE.search(name):
        return PLANT
    if group == 18 and LEAVENING.search(name):
        return PLANT
    if group == 8 and PLAIN_CEREAL.search(name):
        return PLANT
    if group == 6 and name and not STOCK.search(name):
        return PLANT  # a sauce or condiment whose name shows no animal part
    if group in SR_VEGETARIAN_GROUPS:
        return VEGETARIAN_ONLY
    return UNCERTAIN


def _text_class(text: str) -> str:
    if MEAT_WORDS.search(text) and not PLANT_EXCEPTIONS.search(text):
        return MEAT
    if ANIMAL_WORDS.search(text) and not PLANT_EXCEPTIONS.search(text):
        return ANIMAL
    return PLANT


_CUISINES_BY_FOOD: dict[int, list[str]] = {}


def _portion_label(portion: dict) -> str:
    unit = (portion.get("measureUnit") or {}).get("name", "")
    amount = portion.get("value") or portion.get("amount") or ""
    label = f"{amount:g} {unit}" if isinstance(amount, (int, float)) else f"{amount} {unit}"
    if unit in ("RACC", "undetermined"):
        return ""
    return f"{label} {portion.get('modifier', '')}".strip()


def _rows(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


if __name__ == "__main__":
    main()
