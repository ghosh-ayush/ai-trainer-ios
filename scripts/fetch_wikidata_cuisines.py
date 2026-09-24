#!/usr/bin/env python3
"""Download dish-to-cuisine links from Wikidata (CC0) for the cuisine tags on bundled foods.

Usage: python3 scripts/fetch_wikidata_cuisines.py <output directory>

Writes <output>/dish_main_labels.csv: every Wikidata item that is a dish, food, soup, bread,
dessert, snack, salad, curry, sandwich or cuisine-specific food, with its main English label
and the cuisine (P2012) or country of origin (P495) it is linked to. Wikidata is CC0 1.0, so
the derived tags may be bundled; nutrition values never come from here (they stay USDA).

The output is an input to the cuisine review, not to the app: the candidate
(USDA food, cuisine) pairs are matched from it, each pair is checked by two reviewers, and
only the kept pairs go into docs/research/cuisine-tags.json, which build_food_data.py reads.
"""

from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "AITrainer-research/1.0 (offline build script)"
FOOD_CLASSES = "wd:Q746549 wd:Q2095 wd:Q41415 wd:Q7802 wd:Q182940 wd:Q749316 wd:Q9266 wd:Q5451 wd:Q6663 wd:Q1778821"
QUERY = f"""
SELECT ?dish ?label ?cuisineLabel WHERE {{
  VALUES ?cls {{ {FOOD_CLASSES} }}
  ?dish wdt:P31|wdt:P279 ?cls .
  {{ ?dish wdt:P2012 ?cuisine }} UNION {{ ?dish wdt:P495 ?cuisine }}
  ?dish rdfs:label ?label . FILTER(LANG(?label) = "en")
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". ?cuisine rdfs:label ?cuisineLabel }}
}}
"""


def main() -> None:
    """Run the query and save the CSV."""
    if len(sys.argv) != 2:
        raise SystemExit("usage: fetch_wikidata_cuisines.py <output directory>")
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    url = f"{ENDPOINT}?{urllib.parse.urlencode({'query': QUERY})}"
    request = urllib.request.Request(url, headers={"Accept": "text/csv", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        (target / "dish_main_labels.csv").write_bytes(response.read())
    print(f"Wrote {target / 'dish_main_labels.csv'}")


if __name__ == "__main__":
    main()
