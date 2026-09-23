"""The content bundle and its gating: which exercises and policies may drive guidance.

Exercises, the progression policy and the program template ship as data in
``fixture_content.json``. The host never sends content; it only says whether
fixtures are permitted (Debug builds). A ``review`` status of ``approved`` is
always usable, ``fixture`` only when permitted, anything else is disabled.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JSON = dict[str, Any]

_BUNDLE: JSON = json.loads(Path(__file__).with_name("fixture_content.json").read_text())


def load_library(permits_fixtures: bool) -> JSON:
    """The library the rules run against: exercises, policy, template and the fixture flag."""
    return {
        "exercises": _BUNDLE["exercises"],
        "policy": _BUNDLE["policy"],
        "template": _BUNDLE["template"],
        "permitsFixtures": permits_fixtures,
    }


def public_library(library: JSON) -> JSON:
    """The ``Library`` record the host displays (names, alternatives, policy version)."""
    return {key: library[key] for key in ("exercises", "policy", "permitsFixtures")}


def is_enabled(review_status: str, library: JSON) -> bool:
    if review_status == "approved":
        return True
    return review_status == "fixture" and bool(library["permitsFixtures"])


def policy_is_enabled(library: JSON) -> bool:
    return is_enabled(library["policy"]["review"], library)


def exercises_by_id(library: JSON) -> dict[str, JSON]:
    return {exercise["id"]: exercise for exercise in library["exercises"]}
