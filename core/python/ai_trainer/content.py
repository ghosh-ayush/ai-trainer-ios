"""Content bundles and their gating: which exercises and policies may drive guidance.

Training content ships as data, one directory per bundle under ``bundles/``:

- ``manifest.json`` — ``id``, ``version``, ``review`` (``fixture`` · ``pending`` ·
  ``approved`` · ``disabled``), ``evidenceBasis``, the ``sources`` it cites and, once
  approved, an ``approval`` record (who, when, on what basis — ADR-006).
- ``content.json`` — ``exercises``, the progression ``policy`` and the program ``template``.

In every bundle except a fixture, each policy and template parameter is a *cited
value* — ``{"value", "source", "locator", "certainty"}`` — or an explicit owner
decision — ``{"value", "source": "owner", "rationale"}``. Each exercise names the
sources behind its inclusion. :func:`bundle_problems` enforces this; the rules only
ever see the resolved plain values.

Selection: an ``approved`` bundle always runs. Without one, the fixture runs, and the
existing gates allow it only when the host permits fixtures (Debug). A ``pending``
bundle never runs — it exists to be reviewed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

JSON = dict[str, Any]

BUNDLES_DIR = Path(__file__).with_name("bundles")
REVIEW_STATES = ("fixture", "pending", "approved", "disabled")
CERTAINTY_GRADES = ("high", "moderate", "low")
OWNER = "owner"
FIXTURE_BUNDLE_ID = "fixture-1"

# Keys that identify or label a record rather than prescribe training; they need no citation.
_IDENTIFIERS = frozenset({"id", "name", "version", "review", "exerciseID", "equipmentKind", "protocolID"})


def load_library(permits_fixtures: bool) -> JSON:
    """The library the rules run against: exercises, policy, template and the fixture flag."""
    bundle = _active_bundle()
    return {
        "exercises": bundle["exercises"],
        "policy": bundle["policy"],
        "template": bundle["template"],
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


# --- bundles ---------------------------------------------------------------------------------


def read_bundle(directory: Path) -> tuple[JSON, JSON]:
    """The raw ``(manifest, content)`` of one bundle directory, exactly as written."""
    manifest: JSON = json.loads((directory / "manifest.json").read_text())
    content: JSON = json.loads((directory / "content.json").read_text())
    return manifest, content


def bundle_problems(manifest: JSON, content: JSON) -> list[str]:
    """Everything that stops a bundle from being loaded; empty when it is well formed."""
    problems: list[str] = []
    review = manifest.get("review")
    if review not in REVIEW_STATES:
        problems.append(f"manifest.review must be one of {REVIEW_STATES}")
    for key in ("id", "version", "evidenceBasis"):
        if not manifest.get(key):
            problems.append(f"manifest.{key} is required")
    if review == "approved":
        approval = manifest.get("approval") or {}
        for key in ("approvedBy", "approvedOn", "basis"):
            if not approval.get(key):
                problems.append(f"manifest.approval.{key} is required for an approved bundle")
    for section in ("exercises", "policy", "template"):
        if section not in content:
            problems.append(f"content.{section} is required")
    if problems or review == "fixture":
        return problems  # fixtures are test data: no citations to check
    sources = manifest.get("sources") or {}
    for key, source in sources.items():
        if not source.get("citation"):
            problems.append(f"manifest.sources.{key}.citation is required")
    if resolve(content["policy"]).get("review") != review:
        problems.append(f"policy.review must match the manifest ({review})")
    for section in ("policy", "template"):
        problems.extend(_citation_problems(content[section], section, sources))
    for exercise in content["exercises"]:
        if exercise.get("review") != review:
            problems.append(f"exercise {exercise.get('id')}: review must match the manifest ({review})")
        citations = exercise.get("sources") or []
        if not citations:
            problems.append(f"exercise {exercise.get('id')}: name at least one source for its inclusion")
        for citation in citations:
            if citation.get("source") not in sources:
                problems.append(f"exercise {exercise.get('id')}: unknown source {citation.get('source')!r}")
    return problems


def cited_parameters(content: JSON) -> list[tuple[str, JSON]]:
    """Every cited value in a bundle's policy and template, as ``(dotted.path, cited value)``."""
    found: list[tuple[str, JSON]] = []
    for section in ("policy", "template"):
        _collect(content[section], section, found)
    return found


def resolve(node: Any) -> Any:
    """Replace every cited value with its plain ``value``, leaving everything else as it is."""
    if isinstance(node, dict):
        if _is_cited(node):
            return resolve(node["value"])
        return {key: resolve(item) for key, item in node.items()}
    if isinstance(node, list):
        return [resolve(item) for item in node]
    return node


def all_bundles() -> dict[str, tuple[JSON, JSON]]:
    """Every bundle shipped with the core, by id, raw."""
    bundles: dict[str, tuple[JSON, JSON]] = {}
    for directory in sorted(path for path in BUNDLES_DIR.iterdir() if path.is_dir()):
        manifest, content = read_bundle(directory)
        bundles[manifest["id"]] = (manifest, content)
    return bundles


@lru_cache(maxsize=1)
def _active_bundle() -> JSON:
    """The approved bundle if one is well formed, otherwise the fixture. Never a pending one.

    Read once per process: the embedded interpreter lives as long as the app.
    """
    bundles = all_bundles()
    approved = [
        (manifest, content)
        for manifest, content in bundles.values()
        if manifest.get("review") == "approved" and not bundle_problems(manifest, content)
    ]
    _, body = approved[-1] if approved else bundles[FIXTURE_BUNDLE_ID]
    resolved: JSON = resolve(body)
    # Citations are for review; the contract's Exercise record carries no ``sources``.
    resolved["exercises"] = [
        {key: value for key, value in exercise.items() if key != "sources"} for exercise in resolved["exercises"]
    ]
    return resolved


def _is_cited(node: JSON) -> bool:
    return "value" in node and "source" in node


def _citation_problems(node: Any, path: str, sources: JSON) -> list[str]:
    if isinstance(node, dict) and _is_cited(node):
        return _cited_value_problems(node, path, sources)
    if isinstance(node, dict):
        problems: list[str] = []
        for key, item in node.items():
            if key not in _IDENTIFIERS:
                problems.extend(_citation_problems(item, f"{path}.{key}", sources))
        return problems
    return [f"{path} needs a source: write it as a cited value or an owner decision"]


def _cited_value_problems(node: JSON, path: str, sources: JSON) -> list[str]:
    if node["source"] == OWNER:
        return [] if node.get("rationale") else [f"{path}: an owner decision needs a rationale"]
    problems = []
    if node["source"] not in sources:
        problems.append(f"{path}: unknown source {node['source']!r}")
    if not node.get("locator"):
        problems.append(f"{path}: say where in the source (section, table or page)")
    if node.get("certainty") not in CERTAINTY_GRADES:
        problems.append(f"{path}: certainty must be one of {CERTAINTY_GRADES}")
    return problems


def _collect(node: Any, path: str, found: list[tuple[str, JSON]]) -> None:
    if isinstance(node, dict) and _is_cited(node):
        found.append((path, node))
    elif isinstance(node, dict):
        for key, item in node.items():
            _collect(item, f"{path}.{key}", found)
