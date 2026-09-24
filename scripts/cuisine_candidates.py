#!/usr/bin/env python3
"""Propose (USDA food, cuisine) pairs for review; the reviewed result is docs/research/cuisine-tags.json.

Usage: python3 scripts/cuisine_candidates.py <dish_main_labels.csv> <output.json>

Two candidate sources, both matched against USDA FNDDS dish names (the only foods suggested):
- ``CUISINE_KEYWORDS``: a short, documented list of dish words per cuisine.
- Wikidata (CC0): dish items linked to a cuisine (P2012) or country of origin (P495), from
  scripts/fetch_wikidata_cuisines.py. A label is used only when it maps to exactly one of the
  app's eight cuisines and has a word that is rare in USDA SR Legacy names (so generic English
  words such as "wrap" or "barbecue" never tag a food).

Candidates are not tags: each pair must then be kept by two independent reviewers before it is
written to docs/research/cuisine-tags.json, which scripts/build_food_data.py reads.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOODS = ROOT / "core/python/ai_trainer/data/foods.json"

CUISINE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "indian": (
        "curry",
        "dal",
        "biryani",
        "paneer",
        "naan",
        "samosa",
        "idli",
        "dosa",
        "chapati",
        "tandoori",
        "masala",
        "chutney",
        "basmati",
        "ghee",
        "palak",
    ),
    "mexican": (
        "taco",
        "burrito",
        "enchilada",
        "tamale",
        "quesadilla",
        "tortilla",
        "nacho",
        "salsa",
        "fajita",
        "chimichanga",
        "tostada",
        "refried",
        "pozole",
        "mexican",
    ),
    "chinese": (
        "lo mein",
        "chow mein",
        "fried rice",
        "egg roll",
        "dumpling",
        "wonton",
        "sweet and sour",
        "kung pao",
        "general tso",
        "chinese",
        "bok choy",
        "stir-fry",
    ),
    "japanese": ("sushi", "teriyaki", "miso", "edamame", "ramen", "udon", "soba", "tempura", "japanese"),
    "korean": ("kimchi", "bibimbap", "bulgogi", "korean"),
    "southeastAsian": ("pad thai", "pho", "thai", "vietnamese", "satay", "lemongrass", "spring roll"),
    "italian": (
        "pasta",
        "spaghetti",
        "lasagna",
        "ravioli",
        "pizza",
        "risotto",
        "gnocchi",
        "pesto",
        "marinara",
        "italian",
        "polenta",
        "minestrone",
    ),
    "mediterranean": ("hummus", "falafel", "tabbouleh", "gyro", "pita", "couscous", "tahini", "greek", "feta"),
}
COUNTRIES = {
    "indian": {"India"},
    "mexican": {"Mexico"},
    "chinese": {"People's Republic of China", "China", "Taiwan", "Hong Kong", "Macau"},
    "japanese": {"Japan"},
    "korean": {"South Korea", "North Korea", "Korea"},
    "southeastAsian": {
        "Thailand",
        "Vietnam",
        "Laos",
        "Cambodia",
        "Myanmar",
        "Malaysia",
        "Indonesia",
        "Philippines",
        "Singapore",
        "Brunei",
    },
    "italian": {"Italy", "San Marino"},
    "mediterranean": {
        "Greece",
        "Turkey",
        "Cyprus",
        "Lebanon",
        "Syria",
        "Israel",
        "State of Palestine",
        "Palestine",
        "Jordan",
        "Egypt",
        "Morocco",
        "Tunisia",
        "Algeria",
        "Libya",
        "Malta",
    },
}
CUISINE_NAMES = {
    "indian": r"indian|punjabi|bengali|gujarati|tamil|kerala|malayali|hyderabadi|goan|mughlai|chettinad|rajasthani|"
    r"maharashtrian|marathi|kashmiri|andhra|telugu|karnataka|kannada|udupi|bihari|odia|oriya|konkani|parsi|"
    r"awadhi|assamese|sindhi",
    "mexican": r"mexican|oaxacan|yucat",
    "chinese": r"chinese|cantonese|sichuan|szechuan|hunan|shanghai|hakka|teochew|fujian|beijing|shandong|jiangsu|"
    r"zhejiang|anhui|taiwanese|hong kong",
    "japanese": r"japanese|okinawan",
    "korean": r"korean",
    "southeastAsian": r"thai|vietnamese|lao|laotian|khmer|cambodian|burmese|malaysian|malay|indonesian|filipino|"
    r"philippine|singaporean|peranakan|javanese|balinese|sundanese|minangkabau",
    "italian": r"italian|sicilian|neapolitan|roman cuisine|venetian|tuscan|ligurian|sardinian|piedmontese|lombard|"
    r"apulian|calabrian",
    "mediterranean": r"greek|turkish|ottoman|lebanese|levantine|mediterranean|cypriot|israeli|palestinian|syrian|"
    r"egyptian|moroccan|tunisian|maghreb|algerian|libyan|maltese|jordanian",
}


def cuisines_of(label: str) -> set[str]:
    """The app cuisines a Wikidata cuisine or country label stands for."""
    found = {cuisine for cuisine, names in COUNTRIES.items() if label in names}
    found |= {cuisine for cuisine, pattern in CUISINE_NAMES.items() if re.search(r"\b(" + pattern + r")", label, re.I)}
    return found


def main() -> None:
    """Write candidate pairs for review."""
    if len(sys.argv) != 3:
        raise SystemExit("usage: cuisine_candidates.py <dish_main_labels.csv> <output.json>")
    table = json.loads(FOODS.read_text())
    foods = [dict(zip(table["fields"], row, strict=True)) for row in table["foods"]]
    by_label: dict[str, set[str]] = defaultdict(set)
    with open(sys.argv[1], newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_label[row["label"].strip().lower()] |= cuisines_of(row["cuisineLabel"])
    sr_words = Counter(
        word for f in foods if f["dataset"] == "srLegacy" for word in set(re.findall(r"[a-z]+", f["name"].lower()))
    )
    labels = sorted(
        (
            label
            for label, found in by_label.items()
            if len(found) == 1
            and len(label) >= 3
            and any(sr_words[word] < 3 for word in re.findall(r"[a-z]+", label) if len(word) >= 3)
        ),
        key=len,
        reverse=True,
    )
    wikidata = re.compile(r"\b(" + "|".join(re.escape(label) for label in labels) + r")\b")
    pairs: dict[tuple[int, str], dict] = {}
    for food in foods:
        if food["dataset"] != "fndds":
            continue
        name = food["name"].lower()
        for cuisine, words in CUISINE_KEYWORDS.items():
            if any(re.search(r"\b" + re.escape(word), name) for word in words):
                pairs.setdefault((food["id"], cuisine), _pair(food, cuisine))["basis"].append("keyword")
        for match in wikidata.finditer(name):
            cuisine = next(iter(by_label[match.group(1)]))
            pairs.setdefault((food["id"], cuisine), _pair(food, cuisine))["basis"].append(f"wikidata:{match.group(1)}")
    Path(sys.argv[2]).write_text(json.dumps(list(pairs.values()), indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {len(pairs)} candidate pairs to {sys.argv[2]}")


def _pair(food: dict, cuisine: str) -> dict:
    return {"foodID": food["id"], "food": food["name"], "category": food["category"], "cuisine": cuisine, "basis": []}


if __name__ == "__main__":
    main()
