#!/usr/bin/env python3
"""Copy the reviewed exercise evidence into the bundled catalog's ``evidence`` fields.

Usage: python3 scripts/annotate_catalog.py          # rewrite exercises.json and the summary
       python3 scripts/annotate_catalog.py --check  # exit 1 if either is stale

Input:  docs/research/exercise-evidence.json (sources and findings, each mapped to catalog ids)
Output: apps/ios/Sources/AITrainerCore/Resources/exercises.json (upstream fields unchanged)
        docs/research/exercise-evidence-summary.md (readable overview)

Run it after ANY change to the evidence file. The tests fail when the two disagree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core/python"))

from ai_trainer import catalog_evidence  # noqa: E402

EVIDENCE_PATH = ROOT / "docs/research/exercise-evidence.json"
CATALOG_PATH = ROOT / "apps/ios/Sources/AITrainerCore/Resources/exercises.json"
SUMMARY_PATH = ROOT / "docs/research/exercise-evidence-summary.md"


def render(records: list[dict]) -> str:
    """The catalog exactly as it is written to disk."""
    return json.dumps(records, indent=2, ensure_ascii=False) + "\n"


def outputs() -> dict[Path, str]:
    """The catalog and summary text the current evidence file produces; raises if the evidence is invalid."""
    catalog = json.loads(CATALOG_PATH.read_text())
    evidence = json.loads(EVIDENCE_PATH.read_text())
    problems = catalog_evidence.evidence_problems(evidence, catalog)
    if problems:
        raise SystemExit("exercise-evidence.json is invalid:\n- " + "\n- ".join(problems))
    return {
        CATALOG_PATH: render(catalog_evidence.annotate(catalog, evidence)),
        SUMMARY_PATH: catalog_evidence.summary(evidence, catalog),
    }


def main() -> None:
    """Rewrite the catalog and summary, or with ``--check`` only report whether they are up to date."""
    expected = outputs()
    if "--check" in sys.argv:
        stale = [path.name for path, text in expected.items() if not path.exists() or path.read_text() != text]
        if stale:
            raise SystemExit(f"{', '.join(stale)} stale: run python3 scripts/annotate_catalog.py")
        return
    for path, text in expected.items():
        path.write_text(text)


if __name__ == "__main__":
    main()
